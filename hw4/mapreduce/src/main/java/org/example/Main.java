package org.example;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Main {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Pattern WORD_PATTERN = Pattern.compile("[A-Za-z]+");
    private static final int PORT = 8080;

    public static void main(String[] args) throws Exception {
        S3Client s3 = S3Client.builder()
                .region(Region.of("us-east-1"))
                .build();

        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);


        server.createContext("/split", ex -> handleSplit(ex, s3));
        server.createContext("/map", ex -> handleMap(ex, s3));
        server.createContext("/reduce", ex -> handleReduce(ex, s3));

        server.start();
        System.out.println("Started on port " + PORT + " region=us-east-1");
    }

    private static void handleSplit(HttpExchange ex, S3Client s3) throws IOException {
        try {
            Map<String, String> q = parseQuery(ex);
            String input = q.get("input");

            S3Ref in = parseS3(input);
            String text = readUtf8(s3, in.bucket, in.key);

            int n = text.length();
            int a = n / 3;
            int b = (2 * n) / 3;

            String p0 = text.substring(0, a);
            String p1 = text.substring(a, b);
            String p2 = text.substring(b);

            String out0 = "hw4/chunks/part0.txt";
            String out1 = "hw4/chunks/part1.txt";
            String out2 = "hw4/chunks/part2.txt";

            writeUtf8(s3, in.bucket, out0, p0);
            writeUtf8(s3, in.bucket, out1, p1);
            writeUtf8(s3, in.bucket, out2, p2);

            writeJson(ex, 200, Map.of(
                    "chunks", List.of(
                            "s3://" + in.bucket + "/" + out0,
                            "s3://" + in.bucket + "/" + out1,
                            "s3://" + in.bucket + "/" + out2
                    )
            ));
        } catch (Exception e) {
            writeJson(ex, 500, Map.of("error", e.toString()));
        }
    }

    private static void handleMap(HttpExchange ex, S3Client s3) throws IOException {
        try {
            Map<String, String> q = parseQuery(ex);
            String input = q.get("input");

            S3Ref in = parseS3(input);
            String text = readUtf8(s3, in.bucket, in.key);

            HashMap<String, Integer> counts = new HashMap<>();
            Matcher m = WORD_PATTERN.matcher(text);
            while (m.find()) {
                String w = m.group().toLowerCase();
                counts.put(w, counts.getOrDefault(w, 0) + 1);
            }

            String safe = in.key.replace("/", "_").replace(".txt", "");
            String outKey = "hw4/maps/" + safe + ".json";

            byte[] json = MAPPER.writeValueAsBytes(counts);
            writeBytes(s3, in.bucket, outKey, json, "application/json");

            writeJson(ex, 200, Map.of("output", "s3://" + in.bucket + "/" + outKey));
        } catch (Exception e) {
            writeJson(ex, 500, Map.of("error", e.toString()));
        }
    }

    private static void handleReduce(HttpExchange ex, S3Client s3) throws IOException {
        try {
            Map<String, String> q = parseQuery(ex);
            String inputs = q.get("inputs");

            String[] arr = inputs.split(",");

            HashMap<String, Integer> merged = new HashMap<>();
            String bucket = null;

            for (String raw : arr) {
                if (raw == null || raw.isBlank()) continue;
                S3Ref in = parseS3(raw.trim());
                bucket = in.bucket;

                byte[] bytes = readBytes(s3, in.bucket, in.key);
                Map<String, Integer> part = MAPPER.readValue(bytes, new TypeReference<Map<String, Integer>>() {});

                for (Map.Entry<String, Integer> e : part.entrySet()) {
                    merged.put(e.getKey(), merged.getOrDefault(e.getKey(), 0) + e.getValue());
                }
            }

            String outKey = "hw4/reduce/final.json";
            byte[] json = MAPPER.writeValueAsBytes(merged);
            writeBytes(s3, bucket, outKey, json, "application/json");

            writeJson(ex, 200, Map.of("output", "s3://" + bucket + "/" + outKey));
        } catch (Exception e) {
            writeJson(ex, 500, Map.of("error", e.toString()));
        }
    }

    private static String readUtf8(S3Client s3, String bucket, String key) {
        byte[] b = readBytes(s3, bucket, key);
        return new String(b, StandardCharsets.UTF_8);
    }

    private static byte[] readBytes(S3Client s3, String bucket, String key) {
        GetObjectRequest req = GetObjectRequest.builder().bucket(bucket).key(key).build();
        ResponseBytes<?> resp = s3.getObjectAsBytes(req);
        return resp.asByteArray();
    }

    private static void writeUtf8(S3Client s3, String bucket, String key, String text) {
        byte[] b = text.getBytes(StandardCharsets.UTF_8);
        writeBytes(s3, bucket, key, b, "text/plain; charset=utf-8");
    }

    private static void writeBytes(S3Client s3, String bucket, String key, byte[] bytes, String contentType) {
        PutObjectRequest put = PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .contentType(contentType)
                .build();
        s3.putObject(put, RequestBody.fromBytes(bytes));
    }


    private static Map<String, String> parseQuery(HttpExchange ex) {
        String raw = ex.getRequestURI().getRawQuery();
        HashMap<String, String> map = new HashMap<>();
        if (raw == null) return map;
        for (String pair : raw.split("&")) {
            int idx = pair.indexOf('=');
            if (idx < 0) continue;
            String k = urlDecode(pair.substring(0, idx));
            String v = urlDecode(pair.substring(idx + 1));
            map.put(k, v);
        }
        return map;
    }

    private static String urlDecode(String s) {
        return URLDecoder.decode(s, StandardCharsets.UTF_8);
    }

    private static void writeJson(HttpExchange ex, int status, Object body) throws IOException {
        byte[] bytes = MAPPER.writeValueAsBytes(body);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }

    private static S3Ref parseS3(String s3uri) {

        String rest = s3uri.substring("s3://".length());
        int idx = rest.indexOf('/');
        if (idx < 0) throw new IllegalArgumentException("bad s3 uri: " + s3uri);
        String bucket = rest.substring(0, idx);
        String key = rest.substring(idx + 1);
        return new S3Ref(bucket, key);
    }

    private static class S3Ref {
        final String bucket;
        final String key;

        S3Ref(String bucket, String key) {
            this.bucket = bucket;
            this.key = key;
        }
    }
}

