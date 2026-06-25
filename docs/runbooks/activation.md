# Runbook — Instance Activation

The onboarding wizard is gated behind **instance activation**. This page explains
how to unlock it, especially when **you are the owner / self-hosting** the box.

## TL;DR — you are blocked at the activation screen

You have three options, fastest first:

| Option | When to use | What to do |
|--------|-------------|------------|
| **A. Disable the gate** | You self-host and don't need licensing | Set `ACTIVATION_REQUIRED=false` in the backend environment, restart. |
| **B. Self-mint a code** | You want to keep the signed-token licensing, with your own key | Run `python scripts/activate.py`, set the printed `ACTIVATION_PUBLIC_KEY_B64` in the backend env, paste the code in the UI. |
| **C. Request a code** | You are a downstream user of someone else's instance | Email your Instance ID to the owner and paste back the code they send. |

---

## Why activation exists

`activation.py` implements an Ed25519-signed licensing gate. A valid activation
token is a JWT signed by the **owner's private key**; the server verifies it
against a trusted **public key**. The token embeds your `instanceId`, so a code
issued for one install cannot be reused on another.

The original flow assumed a separation between *owner* (holds the private key)
and *admin* (runs the box and emails for a code). When you are **both**, that
round trip is a dead end — there was no tool to mint a code. Options A and B
below close that gap.

---

## Option A — disable the gate (self-hosted)

Set the environment variable and restart the backend:

```bash
ACTIVATION_REQUIRED=false
```

- On Render: **Environment → Add** `ACTIVATION_REQUIRED=false` → **Save** → redeploy.
- Locally / Docker: add it to your `.env` or `docker-compose` environment.

`is_activated()` then returns `true` without a signed token and onboarding
unlocks. The signature verification code is **not** weakened — the gate is simply
not enforced while this flag is off. Defaults to `true` (enforced) when unset.

---

## Option B — self-mint a signed code with your own key

Keeps the cryptographic licensing intact, using a keypair you control.

```bash
# Run from the repo root. Reads/creates .instance_id automatically.
python scripts/activate.py --email you@example.com
```

The script:

1. Loads a private key from `ACTIVATION_PRIVATE_KEY_B64`, or `.activation_keypair.json`,
   or **generates a fresh keypair** (saved to `.activation_keypair.json`, git-ignored, `chmod 600`).
2. Mints a token bound to this instance and writes it to `.activation_token`.
3. Prints the **public key** to trust.

Because a freshly generated key is not the one embedded in `activation.py`, make
the server trust it by exporting the printed value in the backend environment:

```bash
ACTIVATION_PUBLIC_KEY_B64="<printed-public-key>"
```

Restart the backend. If you ran the script on the same host as the backend,
`.activation_token` is already installed and onboarding is unlocked. If the
backend runs elsewhere (e.g. Render), use `--print-only`, then paste the printed
token into the **Activation** panel in the UI — the server verifies and persists it.

> Keep `.activation_keypair.json` (and `ACTIVATION_PRIVATE_KEY_B64`) private. The
> private key is what lets you mint codes — for yourself and for any downstream
> users of your instances.

---

## Option C — request a code (downstream user)

1. Copy your **Instance ID** from the activation screen.
2. Email it to the instance owner.
3. Paste the signed code they reply with into the **Activation** panel.

---

## Security notes

- `ACTIVATION_REQUIRED=false` is an **opt-in, off-by-default** escape hatch. It does
  not bypass or weaken signature verification — it only stops enforcing the gate.
- `ACTIVATION_PUBLIC_KEY_B64` lets an operator trust their own key without editing
  source. Set it only to keys you control.
- Generated keypairs and tokens are written with `0600` permissions and are
  git-ignored (`.activation_keypair.json`, `.activation_token`, `.instance_id`).
