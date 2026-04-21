package org.example.scalablenotificationsystem.domain.repository;

import org.example.scalablenotificationsystem.domain.model.OutboxEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface OutboxEventRepository extends JpaRepository<OutboxEvent, String> {
    @Query(
            value = """
                    SELECT *
                    FROM outbox_events
                    WHERE status = :status
                    ORDER BY created_at ASC
                    LIMIT :batchSize
                    FOR UPDATE SKIP LOCKED
                    """,
            nativeQuery = true
    )
    List<OutboxEvent> lockNextBatchByStatus(@Param("status") String status,
                                            @Param("batchSize") int batchSize);
}
