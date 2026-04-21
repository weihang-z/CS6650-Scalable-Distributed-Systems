package org.example.scalablenotificationsystem.infrastructure;

import org.example.scalablenotificationsystem.messaging.event.InAppMessage;

public interface InAppProvider {
    void send(InAppMessage message);
}