output "public_ip" {
  value = aws_eip.album_store.public_ip
}

output "base_url" {
  value = "http://${aws_eip.album_store.public_ip}"
}