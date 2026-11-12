// SPDX-License-Identifier: MPL-2.0

// BirdBox - MCU side.
//
// Drives an FS90R continuous-rotation servo on a linear rail. A small bird is
// mounted on the rail; when BirdNET hears a bird, it is pushed out of the bird
// box hole, held, and retracted. A Modulino Buzzer plays a simulated song for
// the species once the bird is fully out.
//
// The rail has a hard mechanical stop at each end, about 140 degrees of servo
// rotation apart. An FS90R has no position feedback, so every move simply drives
// towards one stop for the full travel time plus a short overrun, and the stop
// does the rest. That makes position tracking and calibration unnecessary: the
// only number to tune is how long the full travel takes.

#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>
#include <Servo.h>

const int PIN_SERVO = 9;

// Trim if the servo creeps when it should be stopped - FS90R units vary.
const int NEUTRAL_US = 1500;
const int MAX_OFFSET_US = 500;  // 500 us off neutral = full speed

// Set to +1 if the rail travels the wrong way for your mounting.
const int OUT_SIGN = -1;

// Optional panel buttons, each wired from the pin to GND. Unconnected pins stay
// high through the pull-up and never trigger.
const int PIN_BUTTONS[] = {2, 3};  // button 1: bird card, button 2: daily summary
const int BUTTON_COUNT = 2;
const unsigned long DEBOUNCE_MS = 30;

// --- Rail ------------------------------------------------------------------

enum RailState { RAIL_UNKNOWN = 0, RAIL_IN = 1, RAIL_OUT = 2, RAIL_MOVING = 3 };
enum Mode { IDLE, MOVING, PRESENT_HOLD };

Servo servo;
Mode mode = IDLE;
RailState rail = RAIL_UNKNOWN;

int speedPct = 40;
long travelMs = 320;     // stop-to-stop time at full speed
long overrunMs = 30;     // extra drive into the stop, so it always seats
long holdMs = 500;       // how long the bird stays out (the minimum, with holdForSong)

// With holdForSong, the bird also stays out until the song has finished, plus a
// short buffer. The cap stops a song upload that never completes from holding
// the bird out forever.
bool holdForSong = true;
const unsigned long SONG_HOLD_BUFFER_MS = 300;
const unsigned long MAX_SONG_HOLD_MS = 15000;

int driveDir = 0;        // -1 in, 0 stopped, +1 out
unsigned long moveEndsAt = 0;
unsigned long holdStartedAt = 0;
unsigned long holdEndsAt = 0;
bool presenting = false; // the out move is part of a detection: hold, then retract

void applyDrive(int dir) {
    driveDir = dir;
    if (dir == 0) {
        if (servo.attached()) {
            servo.detach();  // no pulses at all, so it cannot creep or strain the stop
        }
        return;
    }
    if (!servo.attached()) {
        servo.attach(PIN_SERVO);
    }
    int offset = (long)MAX_OFFSET_US * speedPct / 100;
    servo.writeMicroseconds(NEUTRAL_US + OUT_SIGN * dir * offset);
}

// Drive towards one stop for the scaled travel time plus the overrun.
void startMove(int dir) {
    mode = MOVING;
    rail = RAIL_MOVING;
    moveEndsAt = millis() + (unsigned long)(travelMs * 100 / speedPct) + overrunMs;
    applyDrive(dir);
}

void stopAll() {
    applyDrive(0);
    mode = IDLE;
    presenting = false;
    rail = RAIL_UNKNOWN;  // stopped mid-travel, so neither end is certain
}

// --- Buzzer ----------------------------------------------------------------
// A song is a list of segments, each a sweep from one frequency to another over
// a duration (equal frequencies = a steady note, 0 = a rest). Python sends it in
// chunks because one RPC message is limited to about 256 bytes.

const int MAX_SEGMENTS = 96;
const unsigned long SWEEP_STEP_MS = 10;

struct Segment {
    uint16_t startHz;
    uint16_t endHz;
    uint16_t ms;
};

ModulinoBuzzer buzzer;
bool buzzerFound = false;

Segment song[MAX_SEGMENTS];
int songLength = 0;
int songIndex = -1;           // -1 = not playing
bool songLoading = false;     // between buzzer_clear and buzzer_start / buzzer_arm
bool songArmed = false;       // loaded, waiting for the bird to be fully out
unsigned long songEndedAt = 0;
unsigned long segmentStartedAt = 0;
unsigned long nextStepAt = 0;

bool songBusy() { return songLoading || songArmed || songIndex >= 0; }

void startSegment(unsigned long now);

void startSong(unsigned long now) {
    songArmed = false;
    songIndex = 0;
    startSegment(now);
}

void startSegment(unsigned long now) {
    const Segment& s = song[songIndex];
    segmentStartedAt = now;
    if (s.startHz == 0 || s.startHz == s.endHz) {
        buzzer.tone(s.startHz, s.ms);  // one write covers a rest or a steady note
        nextStepAt = now + s.ms;
    } else {
        buzzer.tone(s.startHz, SWEEP_STEP_MS + 5);
        nextStepAt = now + SWEEP_STEP_MS;
    }
}

void updateSong(unsigned long now) {
    if (songIndex < 0 || now < nextStepAt) {
        return;
    }
    const Segment& s = song[songIndex];
    unsigned long elapsed = now - segmentStartedAt;
    if (elapsed >= s.ms) {
        songIndex++;
        if (songIndex >= songLength) {
            songIndex = -1;
            songEndedAt = now;
            buzzer.tone(0, 10);
            return;
        }
        startSegment(now);
        return;
    }
    // Mid-sweep: step the pitch along the line, overlapping slightly so it never gaps.
    long hz = s.startHz + ((long)s.endHz - s.startHz) * (long)elapsed / s.ms;
    buzzer.tone(hz, SWEEP_STEP_MS + 5);
    nextStepAt = now + SWEEP_STEP_MS;
}

// --- Exposed to Python ---------------------------------------------------
// All registered with provide_safe, so they run between loop() iterations and
// never race the state machine below.

void servo_out() {
    presenting = false;
    startMove(+1);
}

void servo_in() {
    presenting = false;
    startMove(-1);
}

void servo_stop() {
    stopAll();
    songArmed = false;  // no bird coming out, so a waiting song should not fire later
}

// The bird-detection action: out, hold, then back in.
void servo_present() {
    presenting = true;
    startMove(+1);
}

void servo_set_speed(int pct) { speedPct = constrain(pct, 10, 100); }
void servo_set_travel(int ms) { travelMs = constrain(ms, 50, 3000); }
void servo_set_hold(int ms) { holdMs = constrain(ms, 0, 30000); }
void servo_set_overrun(int ms) { overrunMs = constrain(ms, 0, 1000); }
void servo_set_hold_for_song(int on) { holdForSong = on != 0; }

int servo_state() { return (int)rail; }

void buzzer_clear() {
    songIndex = -1;
    songLength = 0;
    songArmed = false;
    songLoading = buzzerFound;
}

// Append "start,end,ms;start,end,ms;..." segments. Returns the song length so
// far, or -1 if no buzzer was found at startup.
int buzzer_add(String chunk) {
    if (!buzzerFound) {
        return -1;
    }
    int pos = 0;
    while (pos < (int)chunk.length() && songLength < MAX_SEGMENTS) {
        int end = chunk.indexOf(';', pos);
        if (end < 0) end = chunk.length();
        String part = chunk.substring(pos, end);
        int c1 = part.indexOf(',');
        int c2 = part.indexOf(',', c1 + 1);
        if (c1 > 0 && c2 > c1) {
            Segment& s = song[songLength++];
            s.startHz = constrain(part.substring(0, c1).toInt(), 0, 20000);
            s.endHz = constrain(part.substring(c1 + 1, c2).toInt(), 0, 20000);
            s.ms = constrain(part.substring(c2 + 1).toInt(), 1, 5000);
        }
        pos = end + 1;
    }
    return songLength;
}

int buzzer_start() {
    songLoading = false;
    if (!buzzerFound || songLength == 0) {
        return 0;
    }
    startSong(millis());
    return songLength;
}

// Like buzzer_start, but the song waits until the bird is fully out (or starts
// at once if the bird is already out and holding).
int buzzer_arm() {
    songLoading = false;
    if (!buzzerFound || songLength == 0) {
        return 0;
    }
    if (mode == PRESENT_HOLD) {
        startSong(millis());
    } else {
        songArmed = true;
    }
    return songLength;
}

void buzzer_stop() {
    if (songIndex >= 0) {
        songEndedAt = millis();
    }
    songIndex = -1;
    songLoading = false;
    songArmed = false;
    if (buzzerFound) {
        buzzer.tone(0, 10);
    }
}

int buzzer_present() { return buzzerFound ? 1 : 0; }

// --- Lifecycle -----------------------------------------------------------

// --- Buttons ---------------------------------------------------------------
// Presses are latched here and collected by the Python app's 0.5 s poll, so a
// quick press is never missed.

bool buttonDown[BUTTON_COUNT];
unsigned long buttonChangedAt[BUTTON_COUNT];
int buttonPresses = 0;  // bit n set: button n+1 pressed since the last poll

void updateButtons(unsigned long now) {
    for (int i = 0; i < BUTTON_COUNT; i++) {
        bool down = digitalRead(PIN_BUTTONS[i]) == LOW;
        if (down != buttonDown[i] && now - buttonChangedAt[i] >= DEBOUNCE_MS) {
            buttonDown[i] = down;
            buttonChangedAt[i] = now;
            if (down) {
                buttonPresses |= 1 << i;
            }
        }
    }
}

int button_presses() {
    int pressed = buttonPresses;
    buttonPresses = 0;
    return pressed;
}

void setup() {
    Monitor.begin(115200);

    pinMode(LED_BUILTIN, OUTPUT);
    for (int i = 0; i < BUTTON_COUNT; i++) {
        pinMode(PIN_BUTTONS[i], INPUT_PULLUP);
    }
    digitalWrite(LED_BUILTIN, HIGH);  // active-low: HIGH is off

    applyDrive(0);

    Modulino.begin(Wire1);
    buzzerFound = buzzer.begin();

    Bridge.begin();
    Bridge.provide_safe("servo_out", servo_out);
    Bridge.provide_safe("servo_in", servo_in);
    Bridge.provide_safe("servo_stop", servo_stop);
    Bridge.provide_safe("servo_present", servo_present);
    Bridge.provide_safe("servo_set_speed", servo_set_speed);
    Bridge.provide_safe("servo_set_travel", servo_set_travel);
    Bridge.provide_safe("servo_set_hold", servo_set_hold);
    Bridge.provide_safe("servo_set_overrun", servo_set_overrun);
    Bridge.provide_safe("servo_set_hold_for_song", servo_set_hold_for_song);
    Bridge.provide_safe("servo_state", servo_state);
    Bridge.provide_safe("buzzer_clear", buzzer_clear);
    Bridge.provide_safe("buzzer_add", buzzer_add);
    Bridge.provide_safe("buzzer_start", buzzer_start);
    Bridge.provide_safe("buzzer_arm", buzzer_arm);
    Bridge.provide_safe("buzzer_stop", buzzer_stop);
    Bridge.provide_safe("buzzer_present", buzzer_present);
    Bridge.provide_safe("button_presses", button_presses);

    Monitor.println(buzzerFound ? "Buzzer found" : "No Modulino Buzzer found");

    // Seat the rail against the inner stop, so every boot starts from a known end.
    startMove(-1);
    Monitor.println("BirdBox servo ready, retracting");
}

void loop() {
    unsigned long now = millis();

    digitalWrite(LED_BUILTIN, mode == IDLE ? HIGH : LOW);
    updateButtons(now);
    updateSong(now);

    switch (mode) {
        case MOVING:
            if ((long)(now - moveEndsAt) >= 0) {
                int arrivedAt = driveDir;
                applyDrive(0);
                rail = arrivedAt > 0 ? RAIL_OUT : RAIL_IN;
                if (presenting && arrivedAt > 0) {
                    mode = PRESENT_HOLD;
                    holdStartedAt = now;
                    holdEndsAt = now + holdMs;
                    if (songArmed) {
                        startSong(now);  // the bird is out: now it sings
                    }
                } else {
                    mode = IDLE;
                    presenting = false;
                }
            }
            break;

        case PRESENT_HOLD: {
            bool done = (long)(now - holdEndsAt) >= 0;
            if (done && holdForSong) {
                // Stay out while the song plays, then for the buffer after it ends.
                bool songOver = !songBusy() && (long)(now - (songEndedAt + SONG_HOLD_BUFFER_MS)) >= 0;
                done = songOver || now - holdStartedAt >= MAX_SONG_HOLD_MS;
            }
            if (done) {
                presenting = false;
                startMove(-1);
            }
            break;
        }

        case IDLE:
            break;
    }
}
