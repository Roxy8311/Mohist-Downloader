/*
 * Decompiled with CFR 0.152.
 */
package org.bukkit.craftbukkit.bootstrap;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.OpenOption;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.FileAttribute;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public class Main {
    public static void main(String[] argv) {
        new Main().run(argv);
    }

    private void run(String[] argv) {
        try {
            String defaultMainClassName = this.readResource("main-class", BufferedReader::readLine);
            String mainClassName = System.getProperty("bundlerMainClass", defaultMainClassName);
            String repoDir = System.getProperty("bundlerRepoDir", "bundler");
            Path outputDir = Paths.get(repoDir, new String[0]).toAbsolutePath();
            if (!Files.isDirectory(outputDir, new LinkOption[0])) {
                Files.createDirectories(outputDir, new FileAttribute[0]);
            }
            System.out.println("Unbundling libraries to " + outputDir);
            boolean readOnly = Boolean.getBoolean("bundlerReadOnly");
            ArrayList<URL> extractedUrls = new ArrayList<URL>();
            this.readAndExtractDir("versions", outputDir, extractedUrls, readOnly);
            this.readAndExtractDir("libraries", outputDir, extractedUrls, readOnly);
            if (mainClassName == null || mainClassName.isEmpty()) {
                System.out.println("Empty main class specified, exiting");
                System.exit(0);
            }
            URLClassLoader classLoader = new URLClassLoader(extractedUrls.toArray(new URL[0]));
            System.out.println("Starting server");
            Thread runThread = new Thread(() -> {
                try {
                    Class<?> mainClass = Class.forName(mainClassName, true, classLoader);
                    MethodHandle mainHandle = MethodHandles.lookup().findStatic(mainClass, "main", MethodType.methodType(Void.TYPE, String[].class)).asFixedArity();
                    mainHandle.invoke(argv);
                }
                catch (Throwable t) {
                    Thrower.INSTANCE.sneakyThrow(t);
                }
            }, "ServerMain");
            runThread.setContextClassLoader(classLoader);
            runThread.start();
        }
        catch (Exception e) {
            e.printStackTrace(System.out);
            System.out.println("Failed to extract server libraries, exiting");
        }
    }

    private <T> T readResource(String resource, ResourceParser<T> parser) throws Exception {
        String fullPath = "/META-INF/" + resource;
        Throwable throwable = null;
        Object var5_6 = null;
        try (InputStream is = this.getClass().getResourceAsStream(fullPath);){
            if (is == null) {
                throw new IllegalStateException("Resource " + fullPath + " not found");
            }
            return parser.parse(new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8)));
        }
        catch (Throwable throwable2) {
            if (throwable == null) {
                throwable = throwable2;
            } else if (throwable != throwable2) {
                throwable.addSuppressed(throwable2);
            }
            throw throwable;
        }
    }

    private void readAndExtractDir(String subdir, Path outputDir, List<URL> extractedUrls, boolean readOnly) throws Exception {
        List entries = this.readResource(String.valueOf(subdir) + ".list", reader -> reader.lines().map(FileEntry::parseLine).toList());
        Path subdirPath = outputDir.resolve(subdir);
        for (FileEntry entry : entries) {
            if (entry.path.startsWith("minecraft-server")) continue;
            Path outputFile = subdirPath.resolve(entry.path);
            if (!readOnly) {
                this.checkAndExtractJar(subdir, entry, outputFile);
            }
            extractedUrls.add(outputFile.toUri().toURL());
        }
    }

    private void checkAndExtractJar(String subdir, FileEntry entry, Path outputFile) throws Exception {
        if (!Files.exists(outputFile, new LinkOption[0]) || !Main.checkIntegrity(outputFile, entry.hash())) {
            System.out.printf("Unpacking %s (%s:%s) to %s%n", entry.path, subdir, entry.id, outputFile);
            this.extractJar(subdir, entry.path, outputFile);
        }
    }

    private void extractJar(String subdir, String jarPath, Path outputFile) throws IOException {
        Files.createDirectories(outputFile.getParent(), new FileAttribute[0]);
        Throwable throwable = null;
        Object var5_6 = null;
        try (InputStream input = this.getClass().getResourceAsStream("/META-INF/" + subdir + "/" + jarPath);){
            if (input == null) {
                throw new IllegalStateException("Declared library " + jarPath + " not found");
            }
            Files.copy(input, outputFile, StandardCopyOption.REPLACE_EXISTING);
        }
        catch (Throwable throwable2) {
            if (throwable == null) {
                throwable = throwable2;
            } else if (throwable != throwable2) {
                throwable.addSuppressed(throwable2);
            }
            throw throwable;
        }
    }

    /*
     * Enabled aggressive block sorting
     * Enabled unnecessary exception pruning
     * Enabled aggressive exception aggregation
     */
    private static boolean checkIntegrity(Path file, String expectedHash) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        Throwable throwable = null;
        Object var4_5 = null;
        try (InputStream output = Files.newInputStream(file, new OpenOption[0]);){
            output.transferTo(new DigestOutputStream(OutputStream.nullOutputStream(), digest));
            String actualHash = Main.byteToHex(digest.digest());
            if (actualHash.equalsIgnoreCase(expectedHash)) {
                return true;
            }
            System.out.printf("Expected file %s to have hash %s, but got %s%n", file, expectedHash, actualHash);
            return false;
        }
        catch (Throwable throwable3) {
            if (throwable == null) {
                throwable = throwable3;
                throw throwable;
            }
            if (throwable == throwable3) throw throwable;
            throwable.addSuppressed(throwable3);
            throw throwable;
        }
    }

    private static String byteToHex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        byte[] byArray = bytes;
        int n = bytes.length;
        int n2 = 0;
        while (n2 < n) {
            byte b = byArray[n2];
            result.append(Character.forDigit(b >> 4 & 0xF, 16));
            result.append(Character.forDigit(b >> 0 & 0xF, 16));
            ++n2;
        }
        return result.toString();
    }

    private record FileEntry(String hash, String id, String path) {
        public static FileEntry parseLine(String line) {
            String[] fields = line.split(" ");
            if (fields.length != 2) {
                throw new IllegalStateException("Malformed library entry: " + line);
            }
            String path = fields[1].substring(1);
            return new FileEntry(fields[0], path, path);
        }
    }

    @FunctionalInterface
    private static interface ResourceParser<T> {
        public T parse(BufferedReader var1) throws Exception;
    }

    private static class Thrower<T extends Throwable> {
        private static final Thrower<RuntimeException> INSTANCE = new Thrower();

        private Thrower() {
        }

        public void sneakyThrow(Throwable exception) throws T {
            throw exception;
        }
    }
}

