package org.example.scalablenotificationsystem.api.dto;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

public record NotificationRequest(
        @NotBlank String tenantId,
        @NotBlank String userId,
        @NotBlank String eventType,
        @NotEmpty List<String> channels,
        @NotBlank String payloadJson
) {
}
