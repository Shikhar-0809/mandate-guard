const API_URL = "http://localhost:8000/check";
const TRACE_DELAY_MS = 250;

function freshDates() {
  const now = new Date();
  const issued = new Date(now);
  issued.setDate(issued.getDate() - 7);
  const expires = new Date(now);
  expires.setDate(expires.getDate() + 30);
  return {
    intent_issued_at: issued.toISOString().slice(0, 19),
    intent_expires_at: expires.toISOString().slice(0, 19),
  };
}

function baseRecord(overrides) {
  const dates = freshDates();
  return {
    record_id: "demo-record",
    delegation_token_id: null,
    intent_mandate_id: "demo-mandate-001",
    intent_principal_id: "demo-principal-001",
    intent_scope_merchants: ["amazon.in", "flipkart.com"],
    intent_scope_categories: ["electronics", "groceries"],
    intent_scope_max_amount_minor_units: 8000,
    intent_scope_max_amount_currency: "INR",
    intent_issued_at: dates.intent_issued_at,
    intent_expires_at: dates.intent_expires_at,
    intent_cart_hash: "demo-hash-approved",
    purchase_intent: "",
    cart_mandate_id: "demo-mandate-001",
    cart_items: [
      {
        sku: "ZZ-SKU-DEMO",
        name: "Demo Product",
        quantity: 1,
        unit_price_minor_units: 1500,
        unit_price_currency: "INR",
      },
    ],
    cart_total_minor_units: 1500,
    cart_total_currency: "INR",
    cart_hash: "demo-hash-approved",
    merchant_id: "amazon.in",
    mcc: "electronics",
    transaction_amount_minor_units: 1500,
    transaction_amount_currency: "INR",
    ...overrides,
  };
}

const SCENARIOS = [
  {
    name: "Legitimate purchase",
    build() {
      return baseRecord({
        record_id: "demo-legitimate",
        purchase_intent: "buy wireless mouse",
        intent_scope_max_amount_minor_units: 5000,
        intent_cart_hash: "demo-hash-legit",
        cart_hash: "demo-hash-legit",
        cart_items: [
          {
            sku: "ZZ-SKU-WMOUSE",
            name: "Wireless Mouse",
            quantity: 1,
            unit_price_minor_units: 2500,
            unit_price_currency: "INR",
          },
        ],
        cart_total_minor_units: 2500,
        transaction_amount_minor_units: 2500,
        merchant_id: "amazon.in",
        mcc: "electronics",
      });
    },
  },
  {
    name: "Amount over cap",
    build() {
      return baseRecord({
        record_id: "demo-amount-over-cap",
        purchase_intent: "buy office chair cushion",
        intent_scope_max_amount_minor_units: 2000,
        intent_cart_hash: "demo-hash-cap",
        cart_hash: "demo-hash-cap",
        cart_items: [
          {
            sku: "ZZ-SKU-CUSHION",
            name: "Ergonomic Chair Cushion",
            quantity: 1,
            unit_price_minor_units: 1200,
            unit_price_currency: "INR",
          },
        ],
        cart_total_minor_units: 1200,
        transaction_amount_minor_units: 4500,
        merchant_id: "flipkart.com",
        mcc: "electronics",
      });
    },
  },
  {
    name: "Wrong merchant",
    build() {
      return baseRecord({
        record_id: "demo-wrong-merchant",
        purchase_intent: "purchase USB keyboard",
        intent_scope_merchants: ["amazon.in", "flipkart.com"],
        intent_cart_hash: "demo-hash-merchant",
        cart_hash: "demo-hash-merchant",
        cart_items: [
          {
            sku: "ZZ-SKU-KBOARD",
            name: "USB Keyboard",
            quantity: 1,
            unit_price_minor_units: 1800,
            unit_price_currency: "INR",
          },
        ],
        cart_total_minor_units: 1800,
        transaction_amount_minor_units: 1800,
        merchant_id: "evil-shop.example.com",
        mcc: "electronics",
      });
    },
  },
  {
    name: "Cart tampered after approval",
    build() {
      return baseRecord({
        record_id: "demo-cart-tampered",
        purchase_intent: "buy notebook pack",
        intent_cart_hash: "demo-hash-approved-original",
        cart_hash: "demo-hash-tampered-after-approval",
        cart_items: [
          {
            sku: "ZZ-SKU-NOTEBOOK",
            name: "Notebook Pack (12)",
            quantity: 2,
            unit_price_minor_units: 450,
            unit_price_currency: "INR",
          },
        ],
        cart_total_minor_units: 900,
        transaction_amount_minor_units: 900,
        merchant_id: "flipkart.com",
        mcc: "groceries",
      });
    },
  },
  {
    name: "Brand substitution",
    build() {
      return baseRecord({
        record_id: "demo-brand-substitution",
        purchase_intent: "buy Sony noise cancelling headphones",
        intent_scope_max_amount_minor_units: 15000,
        intent_cart_hash: null,
        cart_hash: "demo-hash-sony-bose",
        cart_items: [
          {
            sku: "ZZ-SKU-BOSE",
            name: "Bose QuietComfort Headphones",
            quantity: 1,
            unit_price_minor_units: 3200,
            unit_price_currency: "INR",
          },
        ],
        cart_total_minor_units: 3200,
        transaction_amount_minor_units: 3200,
        merchant_id: "amazon.in",
        mcc: "electronics",
      });
    },
  },
  {
    name: "Post-auth SKU swap",
    build() {
      const sharedHash = "demo-hash-post-auth-swap";
      return baseRecord({
        record_id: "demo-post-auth-sku-swap",
        purchase_intent: "order Green Tea",
        intent_scope_max_amount_minor_units: 12000,
        intent_cart_hash: sharedHash,
        cart_hash: sharedHash,
        cart_items: [
          {
            sku: "ZZ-SKU-POWER-BANK",
            name: "Power Bank",
            quantity: 4,
            unit_price_minor_units: 173,
            unit_price_currency: "INR",
          },
        ],
        cart_total_minor_units: 692,
        transaction_amount_minor_units: 1176,
        merchant_id: "flipkart.com",
        mcc: "groceries",
      });
    },
  },
];

let currentRecord = null;
let rawOpen = false;

function $(id) {
  return document.getElementById(id);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function splitList(value) {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function populateForm(record) {
  $("purchase_intent").value = record.purchase_intent || "";
  $("merchant_id").value = record.merchant_id || "";
  $("mcc").value = record.mcc || "";
  const item = record.cart_items[0];
  $("item_sku").value = item.sku;
  $("item_name").value = item.name;
  $("item_quantity").value = String(item.quantity);
  $("item_price").value = String(item.unit_price_minor_units);
  $("transaction_amount").value = String(record.transaction_amount_minor_units);
  $("scope_merchants").value = (record.intent_scope_merchants || []).join(", ");
  $("scope_categories").value = (record.intent_scope_categories || []).join(", ");
  $("scope_max_amount").value = String(record.intent_scope_max_amount_minor_units);
}

function readRecordFromForm() {
  const dates = freshDates();
  const qty = parseInt($("item_quantity").value, 10) || 1;
  const unitPrice = parseInt($("item_price").value, 10) || 0;
  const cartTotal = qty * unitPrice;
  const hashBase = currentRecord || baseRecord({});

  return {
    record_id: hashBase.record_id,
    delegation_token_id: null,
    intent_mandate_id: hashBase.intent_mandate_id,
    intent_principal_id: hashBase.intent_principal_id,
    intent_scope_merchants: splitList($("scope_merchants").value),
    intent_scope_categories: splitList($("scope_categories").value),
    intent_scope_max_amount_minor_units: parseInt($("scope_max_amount").value, 10) || 0,
    intent_scope_max_amount_currency: "INR",
    intent_issued_at: dates.intent_issued_at,
    intent_expires_at: dates.intent_expires_at,
    intent_cart_hash: hashBase.intent_cart_hash,
    purchase_intent: $("purchase_intent").value,
    cart_mandate_id: hashBase.cart_mandate_id,
    cart_items: [
      {
        sku: $("item_sku").value,
        name: $("item_name").value,
        quantity: qty,
        unit_price_minor_units: unitPrice,
        unit_price_currency: "INR",
      },
    ],
    cart_total_minor_units: cartTotal,
    cart_total_currency: "INR",
    cart_hash: hashBase.cart_hash,
    merchant_id: $("merchant_id").value,
    mcc: $("mcc").value,
    transaction_amount_minor_units: parseInt($("transaction_amount").value, 10) || 0,
    transaction_amount_currency: "INR",
  };
}

function resetTrace() {
  ["t0", "t1", "t2"].forEach((tier) => {
    const row = $(`trace-${tier}`);
    row.classList.remove("active");
    $(`status-${tier}`).textContent = "";
  });
  $("verdict-empty").style.display = "flex";
  $("verdict-empty").textContent = "Run a check to see the result";
  const result = $("verdict-result");
  result.className = "verdict-result";
  $("verdict-word").textContent = "";
  $("verdict-word").className = "verdict-word";
  $("reason-code").textContent = "";
  $("t1-stat-value").textContent = "";
  $("t1-stat-value").className = "stat-value";
  $("t2-stat").hidden = true;
  $("t2-stat-value").textContent = "";
  $("raw-json").textContent = "";
}

function showVerdict(data, enableT2, isError) {
  $("verdict-empty").style.display = "none";
  const result = $("verdict-result");
  const verdictClass = isError ? "ERROR" : data.verdict;
  result.className = `verdict-result visible ${verdictClass}`;

  const word = $("verdict-word");
  word.textContent = isError ? "Error" : data.verdict;
  word.className = `verdict-word ${verdictClass}`;

  $("reason-code").textContent = isError ? data.message || data.reason_code : data.reason_code;

  const t1Value = $("t1-stat-value");
  if (isError) {
    t1Value.textContent = "—";
    t1Value.className = "stat-value muted";
  } else if (data.t0_triggered || data.t1_score === null || data.t1_score === undefined) {
    t1Value.textContent = "not reached";
    t1Value.className = "stat-value muted";
  } else {
    t1Value.textContent = data.t1_score.toFixed(3);
    t1Value.className = "stat-value";
  }

  const t2Stat = $("t2-stat");
  if (!isError && enableT2 && data.t2_evidence) {
    t2Stat.hidden = false;
    $("t2-stat-value").textContent = data.t2_evidence;
  } else {
    t2Stat.hidden = true;
    $("t2-stat-value").textContent = "";
  }

  if (!isError) {
    $("raw-json").textContent = JSON.stringify(data, null, 2);
  }
}

function showTraceError(message) {
  resetTrace();
  showVerdict({ message }, false, true);
}

function activateRow(tier, statusText) {
  const row = $(`trace-${tier}`);
  const status = $(`status-${tier}`);
  row.classList.add("active");
  status.textContent = statusText;
}

async function animateTrace(data, enableT2) {
  resetTrace();
  $("verdict-empty").textContent = "Running check…";
  $("verdict-empty").style.display = "flex";

  showVerdict(data, enableT2, false);

  if (data.t0_triggered) {
    activateRow("t0", "BLOCK");
    await delay(TRACE_DELAY_MS);
    activateRow("t1", "not reached");
    await delay(TRACE_DELAY_MS);
    activateRow("t2", "not reached");
    return;
  }

  activateRow("t0", "PASS");
  await delay(TRACE_DELAY_MS);

  if (data.t1_score !== null && data.t1_score !== undefined) {
    activateRow("t1", `score ${data.t1_score.toFixed(3)}`);
  } else {
    activateRow("t1", "not scored");
  }
  await delay(TRACE_DELAY_MS);

  if (!enableT2) {
    activateRow("t2", "not invoked");
  } else if (data.t2_evidence) {
    activateRow("t2", data.t2_evidence);
  } else {
    activateRow("t2", "invoked");
  }
}

async function runCheck() {
  const record = readRecordFromForm();
  const enableT2 = $("enable-t2").checked;

  resetTrace();
  $("verdict-empty").textContent = "Running check…";
  $("verdict-empty").style.display = "flex";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record, enable_t2: enableT2 }),
    });

    if (!response.ok) {
      const errBody = await response.text();
      showTraceError(`API error ${response.status}: ${errBody}`);
      return;
    }

    const data = await response.json();
    await animateTrace(data, enableT2);
  } catch {
    showTraceError(
      "Could not reach the API at localhost:8000 — is it running?"
    );
  }
}

function selectScenario(index) {
  document.querySelectorAll(".scenario-row").forEach((btn, i) => {
    btn.classList.toggle("selected", i === index);
  });
  currentRecord = SCENARIOS[index].build();
  populateForm(currentRecord);
  runCheck();
}

function initScenarioPicker() {
  const picker = $("scenario-picker");
  SCENARIOS.forEach((scenario, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "scenario-row";
    btn.textContent = scenario.name;
    btn.addEventListener("click", () => selectScenario(index));
    picker.appendChild(btn);
  });
}

$("run-check-btn").addEventListener("click", () => runCheck());

$("raw-toggle").addEventListener("click", () => {
  rawOpen = !rawOpen;
  $("raw-json").classList.toggle("open", rawOpen);
  $("raw-toggle").setAttribute("aria-expanded", String(rawOpen));
});

initScenarioPicker();
