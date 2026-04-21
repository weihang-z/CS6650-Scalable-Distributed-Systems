package org.example.scalablenotificationsystem.application;

import org.example.scalablenotificationsystem.messaging.event.EmailMessage;
import org.example.scalablenotificationsystem.messaging.event.InAppMessage;
import org.example.scalablenotificationsystem.messaging.event.NotificationRequestedEvent;
import org.example.scalablenotificationsystem.messaging.producer.KafkaEventPublisher;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.time.Instant;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "ingress", matchIfMissing = true)
@Service
public class RoutingService {

    private final KafkaEventPublisher kafkaEventPublisher;
    private final JsonSupport jsonSupport;

    @Value("${app.topics.email-send}")
    private String emailSendTopic;

    @Value("${app.topics.inapp-send}")
    private String inAppSendTopic;

    public RoutingService(KafkaEventPublisher kafkaEventPublisher,
                          JsonSupport jsonSupport) {
        this.kafkaEventPublisher = kafkaEventPublisher;
        this.jsonSupport = jsonSupport;
    }

    public void route(NotificationRequestedEvent event) {
        for (String channel : event.channels()) {
            Instant producedAt = Instant.now();

            switch (channel.toUpperCase()) {
                case "EMAIL" -> {
                    EmailMessage emailMessage = new EmailMessage(
                            event.tenantId(),
                            event.notificationId(),
                            event.userId(),
                            event.eventType(),
                            event.payloadJson(),
                            event.apiAcceptedAt(),
                            producedAt
                    );
                    kafkaEventPublisher.publish(
                            emailSendTopic,
                            String.valueOf(event.notificationId()),
                            jsonSupport.toJson(emailMessage)
                    );
                }
                case "INAPP" -> {
                    InAppMessage inAppMessage = new InAppMessage(
                            event.tenantId(),
                            event.notificationId(),
                            event.userId(),
                            event.eventType(),
                            event.payloadJson(),
                            event.apiAcceptedAt(),
                            producedAt
                    );
                    kafkaEventPublisher.publish(
                            inAppSendTopic,
                            String.valueOf(event.notificationId()),
                            jsonSupport.toJson(inAppMessage)
                    );
                }
                default -> throw new IllegalArgumentException("Unsupported channel: " + channel);
            }
        }
    }
}