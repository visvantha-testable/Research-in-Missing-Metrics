package cases;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.Reader;
import java.io.StringReader;
import java.io.StringWriter;
import java.io.Writer;
import java.net.URL;
import java.net.URLConnection;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

public class CouplingBetweenObjectsDemo {
    public void useManyTypes() {
        List<String> list = new ArrayList<>();
        Set<Integer> set = new HashSet<>();
        Map<String, Integer> map = new HashMap<>();
        TreeMap<String, Integer> treeMap = new TreeMap<>();
        LinkedList<String> linked = new LinkedList<>();
        TreeSet<String> treeSet = new TreeSet<>();
        File file = new File("temp.txt");
        Path path = Paths.get("temp.txt");
        URL url = null;
        URLConnection connection = null;
        Reader reader = new StringReader("");
        Writer writer = new StringWriter();
        BufferedReader bufferedReader = new BufferedReader(reader);
        BufferedWriter bufferedWriter = new BufferedWriter(writer);
        InputStream inputStream = new ByteArrayInputStream(new byte[0]);
        OutputStream outputStream = new ByteArrayOutputStream();
        PrintWriter printWriter = new PrintWriter(writer);
        FileReader fileReader = null;
        FileWriter fileWriter = null;
        list.add("value");
        set.add(1);
        map.put("k", 1);
        treeMap.put("k", 1);
        linked.add("v");
        treeSet.add("v");
        System.out.println(file.getName() + path + list + set + map + treeMap + linked + treeSet
                + url + connection + reader + writer + bufferedReader + bufferedWriter
                + inputStream + outputStream + printWriter + fileReader + fileWriter);
    }
}
