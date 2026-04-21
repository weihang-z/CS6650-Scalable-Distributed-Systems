package org.example.scalablenotificationsystem.infrastructure;

import org.example.scalablenotificationsystem.messaging.event.EmailMessage;

public interface EmailProvider {
    void send(EmailMessage message);
}
