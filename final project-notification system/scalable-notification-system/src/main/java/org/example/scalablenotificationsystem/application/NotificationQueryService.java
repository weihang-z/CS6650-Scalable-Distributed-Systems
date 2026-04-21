package org.example.scalablenotificationsystem.application;

import org.example.scalablenotificationsystem.domain.model.NotificationAttempt;
import org.example.scalablenotificationsystem.domain.repository.NotificationAttemptRepository;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.util.List;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "ingress", matchIfMissing = true)
@Service
public class NotificationQueryService {

    private final NotificationAttemptRepository notificationAttemptRepository;

    public NotificationQueryService(NotificationAttemptRepository notificationAttemptRepository) {
        this.notificationAttemptRepository = notificationAttemptRepository;
    }

    public List<NotificationAttempt> getAttempts(Long notificationId) {
        return notificationAttemptRepository.findByNotificationIdOrderByCreatedAtAsc(notificationId);
    }
}