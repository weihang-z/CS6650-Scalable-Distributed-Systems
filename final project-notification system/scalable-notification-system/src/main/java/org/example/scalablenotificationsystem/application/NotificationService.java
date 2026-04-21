package org.example.scalablenotificationsystem.application;

import jakarta.transaction.Transactional;
import org.example.scalablenotificationsystem.api.dto.NotificationRequest;
import org.example.scalablenotificationsystem.api.dto.NotificationResponse;
import org.example.scalablenotificationsystem.domain.model.Notification;
import org.example.scalablenotificationsystem.domain.model.OutboxEvent;
import org.example.scalablenotificationsystem.domain.repository.NotificationRepository;
import org.example.scalablenotificationsystem.domain.repository.OutboxEventRepository;
import org.example.scalablenotificationsystem.messaging.event.NotificationRequestedEvent;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "ingress", matchIfMissing = true)
@Service
public class NotificationService {

    private final NotificationRepository notificationRepository;
    private final OutboxEventRepository outboxEventRepository;
    private final JsonSupport jsonSupport;

    @Value("${app.topics.notification-requested}")
    private String notificationRequestedTopic;

    public NotificationService(NotificationRepository notificationRepository,
                               OutboxEventRepository outboxEventRepository,
                               JsonSupport jsonSupport) {
        this.notificationRepository = notificationRepository;
        this.outboxEventRepository = outboxEventRepository;
        this.jsonSupport = jsonSupport;
    }

    @Transactional
    public NotificationResponse createNotification(NotificationRequest request) {
        Instant acceptedAt = Instant.now();

        Notification notification = new Notification(
                request.tenantId(),
                request.userId(),
                request.eventType(),
                "MULTI_CHANNEL",
                request.payloadJson(),
                "PENDING",
                acceptedAt,
                acceptedAt
        );
        notificationRepository.save(notification);

        NotificationRequestedEvent event = new NotificationRequestedEvent(
                UUID.randomUUID().toString(),
                notification.getId(),
                request.tenantId(),
                request.userId(),
                request.eventType(),
                request.channels(),
                request.payloadJson(),
                acceptedAt
        );

        OutboxEvent outboxEvent = new OutboxEvent(
                "Notification",
                notification.getId().toString(),
                "NotificationRequested",
                notificationRequestedTopic,
                jsonSupport.toJson(event),
                "NEW"
        );
        outboxEventRepository.save(outboxEvent);

        return new NotificationResponse(
                notification.getId(),
                notification.getStatus(),
                "Notification accepted and outbox event created"
        );
    }
}
