package org.example.scalablenotificationsystem.messaging.event;

public record InAppMessage(
        String tenantId,
        Long notificationId,
        String userId,
        String eventType,
        String payloadJson
) {
}