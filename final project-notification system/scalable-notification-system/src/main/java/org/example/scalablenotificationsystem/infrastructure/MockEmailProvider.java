package org.example.scalablenotificationsystem.infrastructure;

import org.example.scalablenotificationsystem.messaging.event.EmailMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class MockEmailProvider implements EmailProvider {

    @Value("${app.providers.email.simulated-latency-ms:100}")
    private long simulatedLatencyMs;

    @Override
    public void send(EmailMessage message) {
        try {
            Thread.sleep(simulatedLatencyMs);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Email provider interrupted", e);
        }
    }
}