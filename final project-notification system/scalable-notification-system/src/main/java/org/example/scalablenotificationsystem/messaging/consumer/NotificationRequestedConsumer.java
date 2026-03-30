package org.example.scalablenotificationsystem.messaging.consumer;

import org.example.scalablenotificationsystem.application.RoutingService;
import org.example.scalablenotificationsystem.messaging.event.NotificationRequestedEvent;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

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
            groupId = "${spring.kafka.consumer.group-id}"
    )
    public void consume(String payloadJson) {
        NotificationRequestedEvent event =
                jsonSupport.fromJson(payloadJson, NotificationRequestedEvent.class);
        routingService.route(event);
    }
}