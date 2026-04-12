resource "aws_key_pair" "album_store" {
  key_name   = "album-store-key"
  public_key = file(pathexpand(var.public_key_path))
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "album_store" {
  name        = "album-store-sg"
  description = "Security group for album store"

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "album_store" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.album_store.key_name
  vpc_security_group_ids      = [aws_security_group.album_store.id]
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              set -eux

              apt-get update
              apt-get install -y mkdir rsync

              mkdir -p /opt/album-store
              mkdir -p /opt/album-store/data/tmp
              mkdir -p /opt/album-store/data/files
              EOF

  tags = {
    Name = "album-store"
  }
}

resource "aws_eip" "album_store" {
  domain = "vpc"
}

resource "aws_eip_association" "album_store" {
  instance_id   = aws_instance.album_store.id
  allocation_id = aws_eip.album_store.id
}

resource "null_resource" "deploy_app" {
  depends_on = [aws_eip_association.album_store]

  triggers = {
    app_binary_sha256 = filesha256(pathexpand(var.app_binary_path))
  }

  connection {
    type        = "ssh"
    host        = aws_eip.album_store.public_ip
    user        = var.ssh_user
    private_key = file(pathexpand(var.private_key_path))
    agent       = false
    timeout     = "5m"
  }

  provisioner "file" {
    source      = var.app_binary_path
    destination = "/tmp/album-store"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mkdir -p /opt/album-store",
      "sudo mkdir -p /opt/album-store/data/tmp",
      "sudo mkdir -p /opt/album-store/data/files",
      "sudo install -m 0755 /tmp/album-store /opt/album-store/album-store",
      "sudo systemctl disable album-store || true",
      "sudo systemctl unmask album-store || true",
      "sudo rm -f /etc/systemd/system/album-store.service",
      "sudo tee /etc/systemd/system/album-store.service > /dev/null <<'EOF'\n[Unit]\nDescription=Album Store\nAfter=network.target\n\n[Service]\nUser=root\nWorkingDirectory=/opt/album-store\nExecStart=/opt/album-store/album-store\nRestart=always\nRestartSec=2\n\n[Install]\nWantedBy=multi-user.target\nEOF",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable album-store",
      "sudo systemctl restart album-store",
      "sleep 2",
      "sudo systemctl --no-pager --full status album-store || true",
      "curl -f http://localhost/health"
    ]
  }
}