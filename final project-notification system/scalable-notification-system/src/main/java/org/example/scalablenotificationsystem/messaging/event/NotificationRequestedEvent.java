package org.example.scalablenotificationsystem.messaging.event;

import java.time.Instant;
import java.util.List;

public record NotificationRequestedEvent(
        String eventId,
        Long notificationId,
        String tenantId,
        String userId,
        String eventType,
        List<String> channels,
        String payloadJson,
        Instant apiAcceptedAt
) {
}
