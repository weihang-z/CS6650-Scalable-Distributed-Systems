package org.example.scalablenotificationsystem.domain.repository;

import org.example.scalablenotificationsystem.domain.model.NotificationAttempt;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface NotificationAttemptRepository extends JpaRepository<NotificationAttempt, Long> {

    List<NotificationAttempt> findByNotificationIdOrderByCreatedAtAsc(Long notificationId);

    int countByNotificationIdAndChannel(Long notificationId, String channel);
}