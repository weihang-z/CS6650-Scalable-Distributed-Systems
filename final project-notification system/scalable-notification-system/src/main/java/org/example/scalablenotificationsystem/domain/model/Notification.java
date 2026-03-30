package org.example.scalablenotificationsystem.domain.model;

import jakarta.persistence.*;

import java.time.Instant;

@Entity
@Table(name = "notifications")
public class Notification {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String tenantId;

    @Column(nullable = false)
    private String userId;

    @Column(nullable = false)
    private String eventType;

    @Column(nullable = false)
    private String channel;

    @Lob
    @Column(nullable = false, columnDefinition = "TEXT")
    private String payloadJson;

    @Column(nullable = false)
    private String status;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @Column(nullable = false)
    private Instant updatedAt;

    protected Notification() {
    }

    public Notification(String tenantId,
                        String userId,
                        String eventType,
                        String channel,
                        String payloadJson,
                        String status) {
        this.tenantId = tenantId;
        this.userId = userId;
        this.eventType = eventType;
        this.channel = channel;
        this.payloadJson = payloadJson;
        this.status = status;
    }

    @PrePersist
    public void onCreate() {
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    @PreUpdate
    public void onUpdate() {
        this.updatedAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public String getTenantId() {
        return tenantId;
    }

    public String getUserId() {
        return userId;
    }

    public String getEventType() {
        return eventType;
    }

    public String getChannel() {
        return channel;
    }

    public String getPayloadJson() {
        return payloadJson;
    }

    public String getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}