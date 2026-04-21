resource "aws_instance" "this" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [var.security_group_id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              set -euxo pipefail
              dnf update -y
              dnf install -y docker
              curl -SL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose
              systemctl enable docker
              systemctl start docker

              LOCAL_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

              mkdir -p /opt/kafka
              cat > /opt/kafka/docker-compose.yml <<EOC
              services:
                zookeeper:
                  image: confluentinc/cp-zookeeper:7.5.0
                  container_name: zookeeper
                  environment:
                    ZOOKEEPER_CLIENT_PORT: 2181
                  ports:
                    - "2181:2181"

                kafka:
                  image: confluentinc/cp-kafka:7.5.0
                  container_name: kafka
                  depends_on:
                    - zookeeper
                  ports:
                    - "9092:9092"
                  environment:
                    KAFKA_BROKER_ID: 1
                    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
                    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092
                    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://$${LOCAL_IP}:9092
                    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
                    KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
              EOC

              cd /opt/kafka
              docker-compose up -d
              EOF

  tags = {
    Name = "${var.name_prefix}-kafka-ec2"
  }
}
