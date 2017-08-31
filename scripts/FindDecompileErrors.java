import javax.tools.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Stream;


public class FindDecompileErrors {
    public static void main(String[] args) throws IOException {
        if (args.length != 4) {
            System.err.println("Invalid number of arguments: " + args.length);
            printHelp(System.err);
            System.exit(1);
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            System.err.println("Unable to find java compiler!");
            System.exit(1);
        }
        List<File> classpath = parseClasspath(args[0]);
        classpath.stream().filter((f) -> !f.exists()).forEach((f) -> {
            System.err.println("Missing file in classpath: " + f);
            System.exit(1);
        });
        File sourceRoot = new File(args[1]);
        if (!sourceRoot.exists()) {
            System.err.println("Missing file: " + sourceRoot);
            System.exit(1);
        }
        File targetSources = new File(args[2]);
        if (!targetSources.exists()) {
            System.err.println("Missing file: " + targetSources);
            System.exit(1);
        }
        File outputFile = new File(args[3]);
        if (outputFile.exists()) {
            System.err.println("Deleting existing output: " + outputFile);
            outputFile.delete();
        }
        DiagnosticCollector<JavaFileObject> diagnostics = null;
        StandardJavaFileManager fileManager = null;
        // We have to periodically clear the file manager and diagnostics or we'll hit an OOME
        int timesUsed = 0;
        List<File> sourceFiles = new ArrayList<>();
        try (Stream<Path> s = Files.walk(targetSources.toPath())) {
            s.filter(Files::isRegularFile).map(Path::toFile).forEach(sourceFiles::add);
        }
        Map<String, Set<String>> errors = new HashMap<>();
        Map<String, List<String>> currentErrors = new HashMap<>();
        int i = 0;
        double lastPercentage = 0;
        for (File sourceFile : sourceFiles) {
            if (timesUsed++ > 15 || fileManager == null) {
                if (fileManager != null) {
                    fileManager.close();
                }
                diagnostics = new DiagnosticCollector<>();
                fileManager = compiler.getStandardFileManager(diagnostics, null, StandardCharsets.UTF_8);
            }
            JavaCompiler.CompilationTask task = compiler.getTask(
                null,
                fileManager,
                diagnostics,
                Arrays.asList("-cp", args[0], "-d", "bin"),
                null,
                fileManager.getJavaFileObjects(sourceFile)
            );
            double percentage = (((double) i++) / sourceFiles.size()) * 100;
            if ((int) percentage != (int) lastPercentage) {
                int numErrors = errors.values().stream().mapToInt(Set::size).sum();
                System.out.print("\rCompiled " + ((int) percentage) + "% with " + numErrors + " errors");
            }
            lastPercentage = percentage;
            if (!task.call()) {
                currentErrors.clear();
                for (Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
                    if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                        File f = new File(diagnostic.getSource().toUri());
                        currentErrors
                            .computeIfAbsent(f.getName(), (name) -> new ArrayList<>())
                            .add(diagnostic.getMessage(null));
                    }
                }
                for (Map.Entry<String, List<String>> entry : currentErrors.entrySet()) {
                    Set<String> errorSet = errors.computeIfAbsent(entry.getKey(), (name) -> new HashSet());
                    if (errorSet != null) {
                        errorSet.addAll(entry.getValue());
                    } else {
                        errors.put(entry.getKey(), new HashSet<>(entry.getValue()));
                    }
                }
                currentErrors.clear();
            }
        }
        try (BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outputFile), StandardCharsets.UTF_8))) {
            writer.write("{\"errors\": ");
            simpleEmitJson(errors, writer);
            writer.write("}");
        }
    }
    
    public static List<File> parseClasspath(String classpath) {
        List<File> result = new ArrayList<>();
        for (String part : classpath.split(":")) {
            result.add(new File(part));
        }
        return result;
    }

    private static void printHelp(PrintStream out) {
        out.println("Usage: java FindDecompileErrors.class [classpath] [sourcepath] [sources] [output file]");
    }

    private static final String[] JSON_ESCAPE_TABLE;
    static {
        Map<Character, String> escapedChars = new HashMap<>();
        escapedChars.put('"', "\\\"");
        escapedChars.put('\\', "\\\\");
        escapedChars.put('/', "\\/");
        escapedChars.put('\b', "\\b");
        escapedChars.put('\t', "\\t");
        escapedChars.put('\f', "\\f");
        escapedChars.put('\n', "\\n");
        escapedChars.put('\r', "\\r");
        JSON_ESCAPE_TABLE = new String[128];
        escapedChars.forEach((target, replacement) -> {
            JSON_ESCAPE_TABLE[(int) target] = replacement;
        });
    }
    private static String jsonEscape(char c) {
        int value = (int) c;
        if (value >= 0 && value < JSON_ESCAPE_TABLE.length) {
            return JSON_ESCAPE_TABLE[value];
        } else {
            return null;
        }
    }
    private static void simpleEmitJson(Object value, Writer out) throws IOException {
        simpleEmitJson(value, out, false);
    }
    private static void simpleEmitJson(Object value, Writer out, boolean bare) throws IOException {
        if (value instanceof String) {
            out.write('"');
            String text = (String) value;
            for (int i = 0; i < text.length(); i++) {
                char c = text.charAt(i);
                String escape = jsonEscape(c);
                if (escape != null) {
                    out.append(escape);
                } else {
                    out.append(c);
                }
            }
            out.write('"');
        } else if (value instanceof Iterable) {
            if (!bare) out.append('[');
            Iterator iter = ((Iterable) value).iterator();
            if (iter.hasNext()) {
                simpleEmitJson(iter.next(), out);
                while (iter.hasNext()) {
                    out.write(", ");
                    simpleEmitJson(iter.next(), out);
                }
            }
            if (!bare) out.append(']');
        } else if (value instanceof Map.Entry) {
            Map.Entry entry = (Map.Entry) value;
            simpleEmitJson((String) entry.getKey(), out);
            out.append(": ");
            simpleEmitJson(entry.getValue(), out);
        } else if (value instanceof Map) {
            out.append('{');
            simpleEmitJson(((Map) value).entrySet(), out, true);
            out.append('}');
        } else {
            throw new UnsupportedOperationException("Unsupported type: " + value.getClass());
        }
    }
}