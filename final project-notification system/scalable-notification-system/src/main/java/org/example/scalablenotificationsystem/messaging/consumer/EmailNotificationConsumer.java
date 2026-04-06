package org.example.scalablenotificationsystem.messaging.consumer;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.example.scalablenotificationsystem.domain.model.Notification;
import org.example.scalablenotificationsystem.domain.repository.NotificationRepository;
import org.example.scalablenotificationsystem.messaging.event.EmailMessage;
import org.springframework.kafka.annotation.DltHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.annotation.RetryableTopic;
import org.springframework.kafka.support.ExponentialBackOffWithMaxRetries;
import org.springframework.retry.annotation.Backoff;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.Optional;

@Component
public class EmailNotificationConsumer {

    private final ObjectMapper objectMapper;
    private final ProcessedMessageRepository processedMessageRepository;
    private final NotificationRepository notificationRepository;
    private final NotificationAttemptRepository notificationAttemptRepository;
    private final ThrottlingService throttlingService;
    private final EmailProvider emailProvider;

    public EmailNotificationConsumer(ObjectMapper objectMapper,
                                     ProcessedMessageRepository processedMessageRepository,
                                     NotificationRepository notificationRepository,
                                     NotificationAttemptRepository notificationAttemptRepository,
                                     ThrottlingService throttlingService,
                                     EmailProvider emailProvider) {
        this.objectMapper = objectMapper;
        this.processedMessageRepository = processedMessageRepository;
        this.notificationRepository = notificationRepository;
        this.notificationAttemptRepository = notificationAttemptRepository;
        this.throttlingService = throttlingService;
        this.emailProvider = emailProvider;
    }

    @RetryableTopic(
            attempts = "4",
            backoff = @Backoff(delay = 1000, multiplier = 2.0)
    )
    @KafkaListener(topics = "notification.email.send", groupId = "email-consumers")
    public void consume(String rawJson) {
        EmailMessage message = deserialize(rawJson);

        String idempotencyKey = buildIdempotencyKey(message);
        boolean firstTime = processedMessageRepository.tryInsert(idempotencyKey, "email-consumer");

        if (!firstTime) {
            return; // duplicate message, safe skip
        }

        throttlingService.checkAndConsumeQuota(message.tenantId(), "EMAIL");

        try {
            validate(message);
            emailProvider.send(message);

            markSuccess(message, null);

        } catch (RetryableNotificationException e) {
            markFailureAttempt(message, e.getMessage());
            throw e;

        } catch (NonRetryableNotificationException e) {
            markFailureAttempt(message, e.getMessage());
            throw e;

        } catch (Exception e) {
            markFailureAttempt(message, e.getMessage());
            throw new RetryableNotificationException("Unexpected email send failure", e);
        }
    }

    @DltHandler
    public void handleDlt(String rawJson) {
        EmailMessage message = deserialize(rawJson);
        markFailed(message, "Moved to DLT after retries exhausted");
    }

    private EmailMessage deserialize(String rawJson) {
        try {
            return objectMapper.readValue(rawJson, EmailMessage.class);
        } catch (Exception e) {
            throw new NonRetryableNotificationException("Failed to deserialize EmailMessage", e);
        }
    }

    private void validate(EmailMessage message) {
        if (message.recipientEmail() == null || message.recipientEmail().isBlank()) {
            throw new NonRetryableNotificationException("recipientEmail is missing");
        }
        if (!message.recipientEmail().contains("@")) {
            throw new NonRetryableNotificationException("recipientEmail is invalid");
        }
    }

    private String buildIdempotencyKey(EmailMessage message) {
        return message.tenantId() + ":" + message.notificationId() + ":EMAIL";
    }

    private void markSuccess(EmailMessage message, String note) {
        Optional<Notification> optional = notificationRepository.findById(message.notificationId());
        optional.ifPresent(notification -> {
            notification.setStatus("SENT");
            notification.setUpdatedAt(Instant.now());
            notificationRepository.save(notification);
        });

        NotificationAttempt attempt = new NotificationAttempt();
        attempt.setNotificationId(message.notificationId());
        attempt.setChannel("EMAIL");
        attempt.setAttemptNo(1); // skeleton，真实项目里应该递增
        attempt.setResult("SUCCESS");
        attempt.setErrorMessage(note);
        attempt.setCreatedAt(Instant.now());
        notificationAttemptRepository.save(attempt);
    }

    private void markFailureAttempt(EmailMessage message, String errorMessage) {
        NotificationAttempt attempt = new NotificationAttempt();
        attempt.setNotificationId(message.notificationId());
        attempt.setChannel("EMAIL");
        attempt.setAttemptNo(1); // skeleton，真实项目里应该递增
        attempt.setResult("FAILED");
        attempt.setErrorMessage(errorMessage);
        attempt.setCreatedAt(Instant.now());
        notificationAttemptRepository.save(attempt);
    }

    private void markFailed(EmailMessage message, String reason) {
        Optional<Notification> optional = notificationRepository.findById(message.notificationId());
        optional.ifPresent(notification -> {
            notification.setStatus("FAILED");
            notification.setUpdatedAt(Instant.now());
            notificationRepository.save(notification);
        });

        NotificationAttempt attempt = new NotificationAttempt();
        attempt.setNotificationId(message.notificationId());
        attempt.setChannel("EMAIL");
        attempt.setAttemptNo(1);
        attempt.setResult("DLT");
        attempt.setErrorMessage(reason);
        attempt.setCreatedAt(Instant.now());
        notificationAttemptRepository.save(attempt);
    }
}