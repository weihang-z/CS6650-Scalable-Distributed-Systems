package org.example.scalablenotificationsystem.application;

import org.example.scalablenotificationsystem.domain.model.OutboxEvent;
import org.example.scalablenotificationsystem.domain.repository.OutboxEventRepository;
import org.example.scalablenotificationsystem.messaging.producer.KafkaEventPublisher;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.List;

@Component
@ConditionalOnProperty(
        name = "app.outbox.publisher.enabled",
        havingValue = "true",
        matchIfMissing = true
)
@ConditionalOnProperty(name = "APP_ROLE", havingValue = "ingress", matchIfMissing = true)
public class OutboxPublisher {
    private static final String NEW_STATUS = "NEW";

    private final OutboxEventRepository outboxEventRepository;
    private final KafkaEventPublisher kafkaEventPublisher;
    private final TransactionTemplate transactionTemplate;
    private final int batchSize;
    private final int maxBatchesPerRun;

    public OutboxPublisher(OutboxEventRepository outboxEventRepository,
                           KafkaEventPublisher kafkaEventPublisher,
                           PlatformTransactionManager transactionManager,
                           @Value("${app.outbox.publisher.batch-size:1000}") int batchSize,
                           @Value("${app.outbox.publisher.max-batches-per-run:20}") int maxBatchesPerRun) {
        this.outboxEventRepository = outboxEventRepository;
        this.kafkaEventPublisher = kafkaEventPublisher;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.batchSize = batchSize;
        this.maxBatchesPerRun = maxBatchesPerRun;
    }

    @Scheduled(fixedDelayString = "${app.outbox.publisher.fixed-delay-ms}")
    public void publishPendingEvents() {
        for (int batchNumber = 0; batchNumber < maxBatchesPerRun; batchNumber++) {
            Integer publishedCount = transactionTemplate.execute(status -> publishNextBatch());
            if (publishedCount == null || publishedCount == 0) {
                return;
            }
            if (publishedCount < batchSize) {
                return;
            }
        }
    }

    private int publishNextBatch() {
        List<OutboxEvent> events = outboxEventRepository.lockNextBatchByStatus(NEW_STATUS, batchSize);

        for (OutboxEvent event : events) {
            kafkaEventPublisher.publish(
                    event.getTopic(),
                    event.getAggregateId(),
                    event.getPayloadJson()
            );
            event.markPublished();
        }

        outboxEventRepository.flush();
        return events.size();
    }
}
