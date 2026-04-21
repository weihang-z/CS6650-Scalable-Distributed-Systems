package org.example.scalablenotificationsystem.messaging.event;

import java.time.Instant;

public record EmailMessage(
        String tenantId,
        Long notificationId,
        String userId,
        String eventType,
        String payloadJson,
        Instant apiAcceptedAt,
        Instant channelMessageProducedAt
) {
}