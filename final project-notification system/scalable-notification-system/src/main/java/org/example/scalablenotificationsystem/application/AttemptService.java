package org.example.scalablenotificationsystem.application;

import org.example.scalablenotificationsystem.domain.model.NotificationAttempt;
import org.example.scalablenotificationsystem.domain.repository.NotificationAttemptRepository;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;

@Service
public class AttemptService {

    private final NotificationAttemptRepository notificationAttemptRepository;

    public AttemptService(NotificationAttemptRepository notificationAttemptRepository) {
        this.notificationAttemptRepository = notificationAttemptRepository;
    }

    public void recordAttempt(Long notificationId,
                              String channel,
                              Instant apiAcceptedAt,
                              Instant channelMessageProducedAt,
                              Instant consumerStartedAt,
                              Instant consumerFinishedAt,
                              String result,
                              String errorMessage) {

        int attemptNo = notificationAttemptRepository.countByNotificationIdAndChannel(notificationId, channel) + 1;

        long queueWaitLatencyMs =
                Duration.between(channelMessageProducedAt, consumerStartedAt).toMillis();

        long consumerProcessingLatencyMs =
                Duration.between(consumerStartedAt, consumerFinishedAt).toMillis();

        long endToEndLatencyMs =
                Duration.between(apiAcceptedAt, consumerFinishedAt).toMillis();

        NotificationAttempt attempt = new NotificationAttempt(
                notificationId,
                channel,
                attemptNo,
                result,
                errorMessage,
                apiAcceptedAt,
                channelMessageProducedAt,
                consumerStartedAt,
                consumerFinishedAt,
                queueWaitLatencyMs,
                consumerProcessingLatencyMs,
                endToEndLatencyMs
        );

        notificationAttemptRepository.save(attempt);
    }
}