package org.example.scalablenotificationsystem.messaging.consumer;

import org.example.scalablenotificationsystem.application.RoutingService;
import org.example.scalablenotificationsystem.messaging.event.NotificationRequestedEvent;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@ConditionalOnProperty(name = "APP_ROLE", havingValue = "ingress", matchIfMissing = true)
@Component
public class NotificationRequestedConsumer {

    private final RoutingService routingService;
    private final JsonSupport jsonSupport;

    public NotificationRequestedConsumer(RoutingService routingService,
                                         JsonSupport jsonSupport) {
        this.routingService = routingService;
        this.jsonSupport = jsonSupport;
    }

    @KafkaListener(
            topics = "${app.topics.notification-requested}",
            groupId = "${spring.kafka.consumer.group-id}",
            concurrency = "${app.kafka.notification-requested-consumer-concurrency:4}"
    )
    public void consume(String payloadJson) {
        NotificationRequestedEvent event =
                jsonSupport.fromJson(payloadJson, NotificationRequestedEvent.class);
        routingService.route(event);
    }
}