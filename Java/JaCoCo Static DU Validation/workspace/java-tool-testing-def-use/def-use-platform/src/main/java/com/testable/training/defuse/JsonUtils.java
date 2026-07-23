package com.testable.training.defuse;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public final class JsonUtils {
    public static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    private JsonUtils() {
    }

    public static void write(Path path, Object value) throws Exception {
        if (path.getParent() != null) {
            Files.createDirectories(path.getParent());
        }
        MAPPER.writeValue(path.toFile(), value);
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> readMap(Path path) throws Exception {
        return MAPPER.readValue(path.toFile(), LinkedHashMap.class);
    }
}
