package com.testable.training.platform;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilderFactory;
import java.nio.file.Path;

public final class JacocoXmlParser {

    private JacocoXmlParser() {
    }

    public static JacocoCounters parse(Path path) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setValidating(false);
        factory.setNamespaceAware(true);
        Document doc = factory.newDocumentBuilder().parse(path.toFile());
        Element root = doc.getDocumentElement();
        JacocoCounters counters = new JacocoCounters();

        NodeList sessionNodes = root.getElementsByTagName("sessioninfo");
        if (sessionNodes.getLength() > 0) {
            counters.sessionId = ((Element) sessionNodes.item(0)).getAttribute("id");
        }

        applyCounter(root, "LINE", counters);
        applyCounter(root, "BRANCH", counters);
        applyCounter(root, "INSTRUCTION", counters);

        NodeList packages = root.getElementsByTagName("package");
        for (int i = 0; i < packages.getLength(); i++) {
            Element pkg = (Element) packages.item(i);
            NodeList files = pkg.getElementsByTagName("sourcefile");
            for (int j = 0; j < files.getLength(); j++) {
                Element file = (Element) files.item(j);
                NodeList lines = file.getElementsByTagName("line");
                for (int k = 0; k < lines.getLength(); k++) {
                    Element line = (Element) lines.item(k);
                    int mi = parseInt(line.getAttribute("mi"));
                    int ci = parseInt(line.getAttribute("ci"));
                    int mb = parseInt(line.getAttribute("mb"));
                    int cb = parseInt(line.getAttribute("cb"));
                    if (mi > 0 && ci == 0) {
                        counters.ghostLines++;
                    }
                    if (mb > 0 && cb > 0 && cb < mb) {
                        counters.partialBranchLines++;
                    }
                }
            }
        }
        return counters;
    }

    private static void applyCounter(Element root, String type, JacocoCounters counters) {
        int[] values = counterValue(root, type);
        switch (type) {
            case "LINE" -> {
                counters.lineMissed = values[0];
                counters.lineCovered = values[1];
            }
            case "BRANCH" -> {
                counters.branchMissed = values[0];
                counters.branchCovered = values[1];
            }
            case "INSTRUCTION" -> {
                counters.instructionMissed = values[0];
                counters.instructionCovered = values[1];
            }
            default -> {
            }
        }
    }

    private static int[] counterValue(Element root, String type) {
        NodeList nodes = root.getElementsByTagName("counter");
        for (int i = 0; i < nodes.getLength(); i++) {
            Element counter = (Element) nodes.item(i);
            if (type.equals(counter.getAttribute("type"))) {
                return new int[]{parseInt(counter.getAttribute("missed")), parseInt(counter.getAttribute("covered"))};
            }
        }
        return new int[]{0, 0};
    }

    private static int parseInt(String value) {
        if (value == null || value.isBlank()) {
            return 0;
        }
        return Integer.parseInt(value);
    }
}
