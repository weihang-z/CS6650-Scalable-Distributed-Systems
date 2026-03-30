package org.example.scalablenotificationsystem.application;

import jakarta.transaction.Transactional;
import org.example.scalablenotificationsystem.domain.model.OutboxEvent;
import org.example.scalablenotificationsystem.domain.repository.OutboxEventRepository;
import org.example.scalablenotificationsystem.messaging.producer.KafkaEventPublisher;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@ConditionalOnProperty(
        name = "app.outbox.publisher.enabled",
        havingValue = "true",
        matchIfMissing = true
)
public class OutboxPublisher {

    private final OutboxEventRepository outboxEventRepository;
    private final KafkaEventPublisher kafkaEventPublisher;

    public OutboxPublisher(OutboxEventRepository outboxEventRepository,
                           KafkaEventPublisher kafkaEventPublisher) {
        this.outboxEventRepository = outboxEventRepository;
        this.kafkaEventPublisher = kafkaEventPublisher;
    }

    @Scheduled(fixedDelayString = "${app.outbox.publisher.fixed-delay-ms}")
    @Transactional
    public void publishPendingEvents() {
        List<OutboxEvent> events = outboxEventRepository.findTop100ByStatusOrderByCreatedAtAsc("NEW");

        for (OutboxEvent event : events) {
            kafkaEventPublisher.publish(
                    event.getTopic(),
                    event.getAggregateId(),
                    event.getPayloadJson()
            );
            event.markPublished();
        }
    }
}
