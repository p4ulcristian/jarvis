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

(defn type-text [text]
  "Type text using clipboard paste for better compatibility"
  (try
    ;; Use clipboard for more reliable typing of complex text
    (let [toolkit (Toolkit/getDefaultToolkit)
          clipboard (.getSystemClipboard toolkit)
          string-selection (StringSelection. text)]
      (.setContents clipboard string-selection nil)
      ;; Paste using Ctrl+V
      (let [robot (init-robot)]
        (.keyPress robot KeyEvent/VK_CONTROL)
        (.keyPress robot KeyEvent/VK_V)
        (.keyRelease robot KeyEvent/VK_V)
        (.keyRelease robot KeyEvent/VK_CONTROL)
        (Thread/sleep 50)))
    (catch Exception e
      ;; Fallback to character-by-character typing
      (println "Warning: Clipboard paste failed, using character typing:" (.getMessage e))
      (init-robot)
      (doseq [c text]
        (type-char c)))))

(defn type-text-with-delay [text delay-ms]
  "Type text character by character with delay"
  (init-robot)
  (doseq [c text]
    (type-char c)
    (Thread/sleep delay-ms)))
