package org.example.scalablenotificationsystem.domain.model;

import jakarta.persistence.*;
import lombok.Getter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Getter
@Table(name = "outbox_events")
public class OutboxEvent {

    @Id
    private String id;

    @Column(nullable = false)
    private String aggregateType;

    @Column(nullable = false)
    private String aggregateId;

    @Column(nullable = false)
    private String eventType;

    @Column(nullable = false)
    private String topic;

    @Lob
    @Column(nullable = false, columnDefinition = "TEXT")
    private String payloadJson;

    @Column(nullable = false)
    private String status; // NEW / PUBLISHED / FAILED

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    protected OutboxEvent() {
    }

    public OutboxEvent(String aggregateType,
                       String aggregateId,
                       String eventType,
                       String topic,
                       String payloadJson,
                       String status) {
        this.id = UUID.randomUUID().toString();
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.eventType = eventType;
        this.topic = topic;
        this.payloadJson = payloadJson;
        this.status = status;
    }

    @PrePersist
    public void onCreate() {
        this.createdAt = Instant.now();
    }

    public void markPublished() {
        this.status = "PUBLISHED";
    }

    public void markFailed() {
        this.status = "FAILED";
    }
}
