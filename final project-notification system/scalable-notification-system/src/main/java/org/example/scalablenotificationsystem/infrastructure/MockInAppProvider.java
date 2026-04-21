package org.example.scalablenotificationsystem.infrastructure;

import org.example.scalablenotificationsystem.messaging.event.InAppMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class MockInAppProvider implements InAppProvider {

    @Value("${app.providers.inapp.simulated-latency-ms:20}")
    private long simulatedLatencyMs;

    @Override
    public void send(InAppMessage message) {
        try {
            Thread.sleep(simulatedLatencyMs);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("InApp provider interrupted", e);
        }
    }
}