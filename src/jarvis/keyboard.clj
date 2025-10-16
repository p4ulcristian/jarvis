(ns jarvis.keyboard
  (:require [clojure.core.async :as async])
  (:import [com.github.kwhat.jnativehook GlobalScreen]
           [com.github.kwhat.jnativehook.keyboard NativeKeyListener NativeKeyEvent]
           [java.util.logging Level Logger]))

(def ^:private control-pressed (atom false))
(def ^:private other-key-pressed (atom false))
(def ^:private listener-registered (atom false))

;; Suppress JNativeHook logging noise
(try
  (let [logger (Logger/getLogger "com.github.kwhat.jnativehook")]
    (.setLevel logger Level/WARNING))
  (catch Exception e
    (println "Warning: Could not suppress JNativeHook logging")))

(defn create-key-listener [events-chan]
  "Create a NativeKeyListener that emits events to the async channel"
  (reify NativeKeyListener
    (nativeKeyPressed [this event]
      (let [key-code (.getKeyCode event)
            modifiers (.getModifiers event)]
        ;; Check for Ctrl key (key code 17 for left Ctrl, 163 for right Ctrl)
        (if (or (= key-code 17) (= key-code 163))
          (do
            (reset! control-pressed true)
            (reset! other-key-pressed false)
            (async/put! events-chan {:event :ctrl-pressed :timestamp (System/currentTimeMillis)}))
          ;; Some other key was pressed
          (when @control-pressed
            (reset! other-key-pressed true)))))

    (nativeKeyReleased [this event]
      (let [key-code (.getKeyCode event)]
        ;; Check for Ctrl key (key code 17 for left Ctrl, 163 for right Ctrl)
        (when (or (= key-code 17) (= key-code 163))
          ;; Ctrl was released - check if it was pressed alone
          (let [was-alone (not @other-key-pressed)]
            (reset! control-pressed false)
            (reset! other-key-pressed false)
            (if was-alone
              (async/put! events-chan {:event :ctrl-alone :timestamp (System/currentTimeMillis)})
              (async/put! events-chan {:event :ctrl-released :timestamp (System/currentTimeMillis)}))))))

    (nativeKeyTyped [this event]
      ;; We don't need this event
      nil)))

(defn start-keyboard-listener []
  "Start listening for global keyboard events. Returns an async channel of events."
  (if @listener-registered
    (throw (Exception. "Keyboard listener already started"))
    (try
      (GlobalScreen/registerNativeHook)
      (reset! listener-registered true)
      (let [events-chan (async/chan 10)]
        (GlobalScreen/addNativeKeyListener (create-key-listener events-chan))
        events-chan)
      (catch Exception e
        (throw (Exception. (str "Failed to register global keyboard hook: " (.getMessage e)) e))))))

(defn stop-keyboard-listener []
  "Stop listening for keyboard events"
  (when @listener-registered
    (try
      (GlobalScreen/unregisterNativeHook)
      (reset! listener-registered false)
      (catch Exception e
        (println "Error unregistering hook:" (.getMessage e))))))

(defn is-control-pressed? []
  "Check if Ctrl key is currently pressed"
  @control-pressed)
