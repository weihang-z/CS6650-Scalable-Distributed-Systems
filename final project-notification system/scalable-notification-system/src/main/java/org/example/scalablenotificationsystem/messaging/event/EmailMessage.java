package org.example.scalablenotificationsystem.messaging.event;

public record EmailMessage(
        String tenantId,
        Long notificationId,
        String userId,
        String eventType,
        String payloadJson
) {
}