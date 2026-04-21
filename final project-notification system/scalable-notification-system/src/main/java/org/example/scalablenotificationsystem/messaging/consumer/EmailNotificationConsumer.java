package org.example.scalablenotificationsystem.messaging.consumer;

import org.example.scalablenotificationsystem.application.AttemptService;
import org.example.scalablenotificationsystem.infrastructure.EmailProvider;
import org.example.scalablenotificationsystem.messaging.event.EmailMessage;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.time.Instant;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "worker")
@ConditionalOnProperty(name = "CHANNEL", havingValue = "EMAIL")
@Component
public class EmailNotificationConsumer {

    private final JsonSupport jsonSupport;
    private final EmailProvider emailProvider;
    private final AttemptService attemptService;

    public EmailNotificationConsumer(JsonSupport jsonSupport,
                                     EmailProvider emailProvider,
                                     AttemptService attemptService) {
        this.jsonSupport = jsonSupport;
        this.emailProvider = emailProvider;
        this.attemptService = attemptService;
    }

    @KafkaListener(
            topics = "${app.topics.email-send}",
            groupId = "email-worker-group"
    )
    public void consume(String payloadJson) {
        EmailMessage message = jsonSupport.fromJson(payloadJson, EmailMessage.class);

        Instant startedAt = Instant.now();
        try {
            emailProvider.send(message);
            Instant finishedAt = Instant.now();

            attemptService.recordAttempt(
                    message.notificationId(),
                    "EMAIL",
                    message.apiAcceptedAt(),
                    message.channelMessageProducedAt(),
                    startedAt,
                    finishedAt,
                    "SUCCESS",
                    null
            );
        } catch (Exception e) {
            Instant finishedAt = Instant.now();

            attemptService.recordAttempt(
                    message.notificationId(),
                    "EMAIL",
                    message.apiAcceptedAt(),
                    message.channelMessageProducedAt(),
                    startedAt,
                    finishedAt,
                    "FAILED",
                    e.getMessage()
            );

            throw e;
        }
    }
}