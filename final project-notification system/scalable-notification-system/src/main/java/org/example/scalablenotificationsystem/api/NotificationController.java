package org.example.scalablenotificationsystem.api;

import jakarta.validation.Valid;
import org.example.scalablenotificationsystem.api.dto.NotificationRequest;
import org.example.scalablenotificationsystem.api.dto.NotificationResponse;
import org.example.scalablenotificationsystem.application.NotificationService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/notifications")
public class NotificationController {

    private final NotificationService notificationService;

    public NotificationController(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    @PostMapping
    public ResponseEntity<NotificationResponse> createNotification(
            @Valid @RequestBody NotificationRequest request) {
        NotificationResponse response = notificationService.createNotification(request);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }

    @GetMapping("/health")
    public String health() {
        return "ok";
    }
}