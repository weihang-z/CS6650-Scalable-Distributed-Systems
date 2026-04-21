package org.example.scalablenotificationsystem.domain.model;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "notification_attempts")
public class NotificationAttempt {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long notificationId;

    @Column(nullable = false)
    private String channel;

    @Column(nullable = false)
    private int attemptNo;

    @Column(nullable = false)
    private String result; // SUCCESS / FAILED

    @Column(length = 500)
    private String errorMessage;

    @Column(nullable = false)
    private Instant apiAcceptedAt;

    @Column(nullable = false)
    private Instant channelMessageProducedAt;

    @Column(nullable = false)
    private Instant consumerStartedAt;

    @Column(nullable = false)
    private Instant consumerFinishedAt;

    @Column(nullable = false)
    private long queueWaitLatencyMs;

    @Column(nullable = false)
    private long consumerProcessingLatencyMs;

    @Column(nullable = false)
    private long endToEndLatencyMs;

    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    public NotificationAttempt() {
    }

    public NotificationAttempt(Long notificationId,
                               String channel,
                               int attemptNo,
                               String result,
                               String errorMessage,
                               Instant apiAcceptedAt,
                               Instant channelMessageProducedAt,
                               Instant consumerStartedAt,
                               Instant consumerFinishedAt,
                               long queueWaitLatencyMs,
                               long consumerProcessingLatencyMs,
                               long endToEndLatencyMs) {
        this.notificationId = notificationId;
        this.channel = channel;
        this.attemptNo = attemptNo;
        this.result = result;
        this.errorMessage = errorMessage;
        this.apiAcceptedAt = apiAcceptedAt;
        this.channelMessageProducedAt = channelMessageProducedAt;
        this.consumerStartedAt = consumerStartedAt;
        this.consumerFinishedAt = consumerFinishedAt;
        this.queueWaitLatencyMs = queueWaitLatencyMs;
        this.consumerProcessingLatencyMs = consumerProcessingLatencyMs;
        this.endToEndLatencyMs = endToEndLatencyMs;
    }

    @PrePersist
    public void onCreate() {
        this.createdAt = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public Long getNotificationId() {
        return notificationId;
    }

    public String getChannel() {
        return channel;
    }

    public int getAttemptNo() {
        return attemptNo;
    }

    public String getResult() {
        return result;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public Instant getApiAcceptedAt() {
        return apiAcceptedAt;
    }

    public Instant getChannelMessageProducedAt() {
        return channelMessageProducedAt;
    }

    public Instant getConsumerStartedAt() {
        return consumerStartedAt;
    }

    public Instant getConsumerFinishedAt() {
        return consumerFinishedAt;
    }

    public long getQueueWaitLatencyMs() {
        return queueWaitLatencyMs;
    }

    public long getConsumerProcessingLatencyMs() {
        return consumerProcessingLatencyMs;
    }

    public long getEndToEndLatencyMs() {
        return endToEndLatencyMs;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
