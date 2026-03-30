package org.example.scalablenotificationsystem.api.dto;

public record NotificationResponse(
        Long notificationId,
        String status,
        String message
) {
}