package org.example.scalablenotificationsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.example.scalablenotificationsystem.api.dto.NotificationRequest;
import org.example.scalablenotificationsystem.application.NotificationService;
import org.example.scalablenotificationsystem.domain.model.Notification;
import org.example.scalablenotificationsystem.domain.repository.NotificationRepository;
import org.example.scalablenotificationsystem.domain.repository.OutboxEventRepository;
import org.example.scalablenotificationsystem.support.JsonSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class NotificationServiceTest {

    private NotificationRepository notificationRepository;
    private OutboxEventRepository outboxEventRepository;
    private JsonSupport jsonSupport;
    private NotificationService notificationService;

    @BeforeEach
    void setUp() {
        notificationRepository = mock(NotificationRepository.class);
        outboxEventRepository = mock(OutboxEventRepository.class);
        jsonSupport = new JsonSupport(new ObjectMapper());

        notificationService = new NotificationService(
                notificationRepository,
                outboxEventRepository,
                jsonSupport
        );

        ReflectionTestUtils.setField(
                notificationService,
                "notificationRequestedTopic",
                "notification.requested"
        );

        when(notificationRepository.save(any())).thenAnswer(invocation -> {
            Notification notification = invocation.getArgument(0);
            ReflectionTestUtils.setField(notification, "id", 1L);
            return notification;
        });
    }

    @Test
    void shouldSaveNotificationAndOutboxEventTogether() {
        NotificationRequest request = new NotificationRequest(
                "tenantA",
                "user123",
                "ORDER_CONFIRMED",
                List.of("EMAIL", "INAPP"),
                "{\"orderId\":\"o1001\"}"
        );

        notificationService.createNotification(request);

        verify(notificationRepository, times(1)).save(any());
        verify(outboxEventRepository, times(1)).save(any());
    }
}