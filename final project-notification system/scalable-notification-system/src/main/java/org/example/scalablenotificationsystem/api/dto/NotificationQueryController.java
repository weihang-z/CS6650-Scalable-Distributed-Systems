package org.example.scalablenotificationsystem.api.dto;

import org.example.scalablenotificationsystem.application.NotificationQueryService;
import org.example.scalablenotificationsystem.domain.model.NotificationAttempt;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "ingress", matchIfMissing = true)
@RestController
@RequestMapping("/notifications")
public class NotificationQueryController {

    private final NotificationQueryService notificationQueryService;

    public NotificationQueryController(NotificationQueryService notificationQueryService) {
        this.notificationQueryService = notificationQueryService;
    }

    @GetMapping("/{notificationId}/attempts")
    public List<NotificationAttempt> getAttempts(@PathVariable Long notificationId) {
        return notificationQueryService.getAttempts(notificationId);
    }
}