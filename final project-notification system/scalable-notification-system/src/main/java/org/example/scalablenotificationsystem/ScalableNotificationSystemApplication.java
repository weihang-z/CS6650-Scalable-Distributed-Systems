package org.example.scalablenotificationsystem;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ScalableNotificationSystemApplication {

    public static void main(String[] args) {
        SpringApplication.run(ScalableNotificationSystemApplication.class, args);
    }

}
