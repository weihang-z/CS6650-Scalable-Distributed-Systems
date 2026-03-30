package org.example.scalablenotificationsystem.domain.repository;

import org.example.scalablenotificationsystem.domain.model.Notification;
import org.springframework.data.jpa.repository.JpaRepository;

public interface NotificationRepository extends JpaRepository<Notification, Long> {
}
