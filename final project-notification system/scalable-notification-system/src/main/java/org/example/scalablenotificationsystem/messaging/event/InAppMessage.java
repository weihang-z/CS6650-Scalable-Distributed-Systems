package org.example.scalablenotificationsystem.messaging.event;
import java.time.Instant;

public record InAppMessage(
        String tenantId,
        Long notificationId,
        String userId,
        String eventType,
        String payloadJson,
        Instant apiAcceptedAt,
        Instant channelMessageProducedAt
) {
}