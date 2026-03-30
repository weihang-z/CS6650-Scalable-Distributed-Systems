package org.example.scalablenotificationsystem.domain.repository;

import org.example.scalablenotificationsystem.domain.model.OutboxEvent;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.*;

public interface OutboxEventRepository extends JpaRepository<OutboxEvent, String> {
    List<OutboxEvent> findTop100ByStatusOrderByCreatedAtAsc(String status);
}
