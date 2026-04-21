package org.example.scalablenotificationsystem.messaging.consumer;

import org.example.scalablenotificationsystem.application.AttemptService;
import org.example.scalablenotificationsystem.infrastructure.InAppProvider;
import org.example.scalablenotificationsystem.messaging.event.InAppMessage;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.time.Instant;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "worker")
@ConditionalOnProperty(name = "CHANNEL", havingValue = "INAPP")
@Component
public class InAppNotificationConsumer {

    private final JsonSupport jsonSupport;
    private final InAppProvider inAppProvider;
    private final AttemptService attemptService;

    public InAppNotificationConsumer(JsonSupport jsonSupport,
                                     InAppProvider inAppProvider,
                                     AttemptService attemptService) {
        this.jsonSupport = jsonSupport;
        this.inAppProvider = inAppProvider;
        this.attemptService = attemptService;
    }

    @KafkaListener(
            topics = "${app.topics.inapp-send}",
            groupId = "inapp-worker-group"
    )
    public void consume(String payloadJson) {
        InAppMessage message = jsonSupport.fromJson(payloadJson, InAppMessage.class);

        Instant startedAt = Instant.now();
        try {
            inAppProvider.send(message);
            Instant finishedAt = Instant.now();

            attemptService.recordAttempt(
                    message.notificationId(),
                    "INAPP",
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
                    "INAPP",
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