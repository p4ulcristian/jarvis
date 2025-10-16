(ns jarvis.typer
  (:import [java.awt Robot Toolkit]
           [java.awt.event KeyEvent]
           [java.awt.datatransfer StringSelection]))

(def ^:private robot (atom nil))

(defn init-robot []
  "Initialize the Robot for keyboard simulation"
  (when (nil? @robot)
    (reset! robot (Robot.)))
  @robot)

(defn key-code-for-char [c]
  "Get KeyEvent code for a character"
  (let [upper-c (Character/toUpperCase c)]
    (cond
      (= c \space) KeyEvent/VK_SPACE
      (= c \newline) KeyEvent/VK_ENTER
      (= c \.) KeyEvent/VK_PERIOD
      (= c \,) KeyEvent/VK_COMMA
      (= c \') KeyEvent/VK_QUOTE
      (= c \") (int \") ;; VK_QUOTEDBL
      (= c \-) KeyEvent/VK_MINUS
      (= c \=) KeyEvent/VK_EQUALS
      (= c \[) KeyEvent/VK_OPEN_BRACKET
      (= c \]) KeyEvent/VK_CLOSE_BRACKET
      (= c \;) KeyEvent/VK_SEMICOLON
      (= c \/) KeyEvent/VK_SLASH
      (= c \\) KeyEvent/VK_BACK_SLASH
      (and (>= upper-c \A) (<= upper-c \Z))
      (+ KeyEvent/VK_A (- (int upper-c) (int \A)))
      (and (>= c \0) (<= c \9))
      (+ KeyEvent/VK_0 (- (int c) (int \0)))
      :else nil)))

(defn type-char [c]
  "Type a single character using Robot"
  (let [robot (init-robot)
        key-code (key-code-for-char c)
        need-shift (and (not (nil? c))
                       (Character/isUpperCase c)
                       (Character/isLetter c))]
    (if key-code
      (do
        (when need-shift
          (.keyPress robot KeyEvent/VK_SHIFT))
        (.keyPress robot key-code)
        (.keyRelease robot key-code)
        (when need-shift
          (.keyRelease robot KeyEvent/VK_SHIFT))
        (Thread/sleep 5))
      ;; Fallback for unsupported chars - this won't work well but at least tries
      nil)))

(defn type-with-wtype [text]
  "Type text using wtype command (for Wayland)"
  (try
    (println "[DEBUG] Attempting to type with wtype (Wayland)...")
    (flush)
    (let [process (.. (ProcessBuilder. ["wtype" text])
                      (start))]
      (.waitFor process)
      (let [exit-code (.exitValue process)]
        (if (= exit-code 0)
          (do
            (println "[DEBUG] wtype typing succeeded")
            (flush)
            true)
          (do
            (println "[DEBUG] wtype failed with exit code:" exit-code)
            (flush)
            false))))
    (catch Exception e
      (println "[DEBUG] wtype not available or failed:" (.getMessage e))
      (flush)
      false)))

(defn type-with-xdotool [text]
  "Type text using xdotool command (for X11)"
  (try
    (println "[DEBUG] Attempting to type with xdotool (X11)...")
    (flush)
    (let [process (.. (ProcessBuilder. ["xdotool" "type" "--clearmodifiers" "--" text])
                      (start))]
      (.waitFor process)
      (let [exit-code (.exitValue process)]
        (if (= exit-code 0)
          (do
            (println "[DEBUG] xdotool typing succeeded")
            (flush)
            true)
          (do
            (println "[DEBUG] xdotool failed with exit code:" exit-code)
            (flush)
            false))))
    (catch Exception e
      (println "[DEBUG] xdotool not available or failed:" (.getMessage e))
      (flush)
      false)))

(defn type-text [text]
  "Type text using multiple methods for compatibility"
  (println "[DEBUG] Starting typing process...")
  (flush)

  ;; Try wtype first (for Wayland), then xdotool (for X11)
  (if (or (type-with-wtype text) (type-with-xdotool text))
    (println "[DEBUG] Typed successfully")
    ;; Fallback to Robot/clipboard
    (try
      (println "[DEBUG] Trying Java Robot with clipboard...")
      (flush)
      ;; Use clipboard for more reliable typing of complex text
      (let [toolkit (Toolkit/getDefaultToolkit)
            clipboard (.getSystemClipboard toolkit)
            string-selection (StringSelection. text)]
        (.setContents clipboard string-selection nil)
        (println "[DEBUG] Set clipboard contents")
        (flush)
        (Thread/sleep 100) ;; Give clipboard time to be set
        ;; Paste using Ctrl+V
        (let [robot (init-robot)]
          (println "[DEBUG] Robot initialized, pressing Ctrl+V")
          (flush)
          (.keyPress robot KeyEvent/VK_CONTROL)
          (Thread/sleep 50)
          (.keyPress robot KeyEvent/VK_V)
          (Thread/sleep 50)
          (.keyRelease robot KeyEvent/VK_V)
          (Thread/sleep 50)
          (.keyRelease robot KeyEvent/VK_CONTROL)
          (Thread/sleep 100)
          (println "[DEBUG] Typed successfully with Robot")
          (flush)))
      (catch Exception e
        ;; Fallback to character-by-character typing
        (println "[DEBUG] Robot failed, trying character-by-character typing:" (.getMessage e))
        (flush)
        (try
          (init-robot)
          (doseq [c text]
            (type-char c))
          (println "[DEBUG] Typed successfully character-by-character")
          (flush)
          (catch Exception e2
            (println "[ERROR] All typing methods failed:" (.getMessage e2))
            (flush))))))
  (flush))

(defn type-text-with-delay [text delay-ms]
  "Type text character by character with delay"
  (init-robot)
  (doseq [c text]
    (type-char c)
    (Thread/sleep delay-ms)))
