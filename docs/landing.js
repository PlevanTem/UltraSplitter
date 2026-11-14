(() => {
  "use strict";
  const root = document.documentElement;
  const langButton = document.querySelector(".lang-toggle");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const assetRoot = "./docs/assets/";
  const cases = [
    {
      id: "idol",
      category: "character",
      count: 4,
      color: "#eee9e4",
      title: ["偶像角色 · 多视图拆分", "Idol character · multiple views"],
      short: ["角色设定", "Character"],
      kind: "CHARACTER / 01",
      note: [
        "4 个独立主体 · 经批准的重建与透明变体",
        "4 subjects · approved reconstruction & alpha variants",
      ],
      names: [
        ["主视觉", "Hero composition"],
        ["正面", "Front view"],
        ["四分之三侧面", "Three-quarter view"],
        ["背面", "Back view"],
      ],
      ghost: [1, 3],
    },
    {
      id: "uneven",
      category: "character",
      count: 4,
      color: "#eaece2",
      title: ["不均匀角色 · 四向视图", "Uneven character · four views"],
      short: ["四向视图", "Turnaround"],
      kind: "TURNAROUND / 02",
      note: [
        "4 个原图裁切 · 按语义顺序重排",
        "4 source crops · semantically reordered",
      ],
      names: [
        ["正面", "Front"],
        ["左侧面", "Left profile"],
        ["右侧面", "Right profile"],
        ["背面", "Back"],
      ],
      ghost: [0, 3],
    },
    {
      id: "dense",
      category: "prop",
      count: 11,
      color: "#e8ece8",
      title: ["奇幻武器 · 高密度素材", "Fantasy weapons · dense asset sheet"],
      short: ["武器道具", "Weapons"],
      kind: "GAME ASSETS / 03",
      note: [
        "11 个独立主体 · 6 个裁切 + 5 个原像素重排",
        "11 subjects · 6 crops + 5 source composites",
      ],
      names: Array.from({ length: 11 }, (_, i) => [
        `武器 ${String(i + 1).padStart(2, "0")}`,
        `Weapon ${String(i + 1).padStart(2, "0")}`,
      ]),
      ghost: [2, 3],
    },
    {
      id: "clipped",
      category: "collage",
      count: 5,
      color: "#eee9e0",
      title: ["古典拼贴 · 边缘补全", "Classical collage · edge repair"],
      short: ["拼贴补全", "Collage"],
      kind: "COLLAGE / 04",
      note: [
        "5 个独立主体 · 2 个原像素重排 + 3 个批准后重建",
        "5 subjects · 2 source composites + 3 approved reconstructions",
      ],
      names: [
        ["十字架人物", "Crucified figure"],
        ["长袍人物", "Robed figure"],
        ["雕像", "Statue"],
        ["左侧人物", "Left figure"],
        ["坐姿人物组", "Seated group"],
      ],
      ghost: [0, 3],
    },
  ];
  const text = (pair) => pair[root.dataset.lang === "en" ? 1 : 0];
  const sourceURL = (item) => `${assetRoot}case-${item.id}-input.png`;
  const previewURL = (item, i) =>
    `${assetRoot}showcase/${item.id}-${String(i + 1).padStart(2, "0")}.png`;
  const grid = document.querySelector(".case-grid");
  const picker = document.querySelector(".hero-picker");
  const heroOriginal = document.querySelector(".hero-original");
  const heroImage = heroOriginal.querySelector("img");
  const ghosts = [...document.querySelectorAll(".hero-ghost")];
  const dialog = document.querySelector(".fan-dialog");
  const stage = document.querySelector(".fan-stage");
  const origin = document.querySelector(".fan-origin");
  const originImage = origin.querySelector("img");
  const closeButton = document.querySelector(".fan-close");
  const preloadCache = new Map();
  let selected = 0;
  let active = 0;
  let category = "all";
  let returnTarget = null;
  let animations = [];
  let closing = false;
  let generation = 0;

  function preload(item) {
    if (!preloadCache.has(item.id)) {
      preloadCache.set(
        item.id,
        Promise.all(
          Array.from({ length: item.count }, (_, i) => {
            const img = new Image();
            img.src = previewURL(item, i);
            return img.decode().then(
              () => true,
              () => false,
            );
          }),
        ),
      );
    }
    return preloadCache.get(item.id);
  }

  function renderLibrary() {
    grid.replaceChildren();
    cases.forEach((item, index) => {
      const card = document.createElement("article");
      card.className = "case-card";
      card.dataset.category = item.category;
      card.hidden = category !== "all" && category !== item.category;
      card.innerHTML = `<button type="button" class="case-visual" data-open-case="${index}" style="--case-bg:${item.color}">
        <span class="case-kind">${item.kind}</span>
        <img class="case-source" src="${sourceURL(item)}" alt="" loading="lazy" width="280" height="260">
        <img class="case-satellite" src="${previewURL(item, item.ghost[0])}" alt="" loading="lazy" width="95" height="190">
        <span class="case-open" aria-hidden="true">↗</span>
      </button><div class="case-details"><div class="case-title-row"><h3>${text(item.title)}</h3>
        <span class="case-count">${item.count} ${text(["个素材", "ASSETS"])}</span></div><p>${text(item.note)}</p></div>`;
      const button = card.querySelector("button");
      button.setAttribute("aria-haspopup", "dialog");
      button.setAttribute("aria-controls", "fan-dialog");
      button.setAttribute("aria-expanded", "false");
      button.setAttribute(
        "aria-label",
        `${text(["展开案例：", "Expand case: "])}${text(item.title)}`,
      );
      button.addEventListener("click", () => openFan(index, button));
      button.addEventListener("pointerenter", () => preload(item), {
        once: true,
      });
      button.addEventListener("focus", () => preload(item), { once: true });
      grid.append(card);
    });
    updateLibraryStatus();
  }

  function updateLibraryStatus() {
    const count = cases.filter(
      (item) => category === "all" || item.category === category,
    ).length;
    document.querySelector("#library-status").textContent = text([
      `正在展示 ${count} 个案例。点击原图，展开独立素材。`,
      `Showing ${count} cases. Click a source sheet to unfold its assets.`,
    ]);
  }

  function renderPicker() {
    picker.replaceChildren();
    cases.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.heroCase = index;
      button.innerHTML = `<span class="picker-number">0${index + 1}</span>${text(item.short)}`;
      button.setAttribute("aria-pressed", String(index === selected));
      button.addEventListener("click", () => selectHero(index));
      picker.append(button);
    });
  }

  function selectHero(index) {
    selected = index;
    const item = cases[index];
    heroImage.src = sourceURL(item);
    heroImage.alt = text(item.title);
    heroOriginal.setAttribute(
      "aria-label",
      `${text(["点击原图展开：", "Click to unfold: "])}${text(item.title)}`,
    );
    document.querySelector("#hero-asset-count").textContent =
      `${String(item.count).padStart(2, "0")} ${text(["个独立素材", "INDIVIDUAL ASSETS"])}`;
    ghosts.forEach((img, i) => {
      img.src = previewURL(item, item.ghost[i]);
    });
    picker
      .querySelectorAll("button")
      .forEach((button, i) =>
        button.setAttribute("aria-pressed", String(index === i)),
      );
    if (!reduced.matches)
      heroImage.animate(
        [
          { opacity: 0.2, transform: "translateY(9px) scale(.97)" },
          { opacity: 1, transform: "none" },
        ],
        { duration: 420, easing: "cubic-bezier(.22,1,.36,1)" },
      );
    preload(item);
  }

  function stopAnimations() {
    animations.forEach((animation) => animation.cancel());
    animations = [];
  }

  function animate(element, frames, options) {
    const animation = element.animate(frames, {
      ...options,
      duration: reduced.matches ? 0 : options.duration,
      delay: reduced.matches ? 0 : options.delay || 0,
    });
    animations.push(animation);
    return animation;
  }

  function updateFanCopy() {
    const item = cases[active];
    document.querySelector("#fan-title").textContent = text(item.title);
    document.querySelector("#fan-note").textContent = text(item.note);
    document.querySelector(".fan-position").textContent = `0${active + 1} / 04`;
    document.querySelector("#fan-input-link").href = sourceURL(item);
    document.querySelector("#fan-output-link").href =
      `${assetRoot}case-${item.id}-output.png`;
    originImage.alt = text(item.title);
    origin.setAttribute(
      "aria-label",
      text(["点击原图收起素材", "Click source to fold assets"]),
    );
    closeButton.setAttribute("aria-label", text(["关闭案例", "Close case"]));
    document
      .querySelector('[data-step="-1"]')
      .setAttribute("aria-label", text(["上一个案例", "Previous case"]));
    document
      .querySelector('[data-step="1"]')
      .setAttribute("aria-label", text(["下一个案例", "Next case"]));
    stage.querySelectorAll(".fan-item").forEach((button, i) => {
      button.setAttribute(
        "aria-label",
        `${text(cases[active].names[i])} · ${text(["点击放大", "Click to enlarge"])}`,
      );
      button.querySelector(".asset-name").textContent = text(
        cases[active].names[i],
      );
    });
  }

  function layoutFan() {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    const count = cases[active].count;
    const small = width < 600;
    const dense = count > 8;
    const radiusX =
      width * (small ? (dense ? 0.36 : 0.32) : dense ? 0.405 : 0.37);
    const radiusY = small
      ? height * 0.68
      : Math.min(height * 0.61, radiusX * 0.8);
    const itemWidth = dense
      ? Math.min(100, width * (small ? 0.112 : 0.085))
      : Math.min(190, width * (small ? 0.22 : 0.18));
    const itemHeight = dense
      ? Math.min(small ? 90 : 145, height * 0.29)
      : Math.min(small ? 190 : 245, height * (small ? 0.34 : 0.45));
    stage.style.setProperty(
      "--origin-w",
      `${Math.min(small ? 134 : 200, width * 0.28)}px`,
    );
    stage.style.setProperty(
      "--origin-h",
      `${Math.min(small ? 150 : 205, height * 0.34)}px`,
    );
    stage.querySelectorAll(".fan-item").forEach((button, index) => {
      const angle = ((-76 + (index * 152) / (count - 1)) * Math.PI) / 180;
      button.style.setProperty("--x", `${Math.sin(angle) * radiusX}px`);
      button.style.setProperty("--y", `${-Math.cos(angle) * radiusY}px`);
      button.style.setProperty(
        "--tilt",
        `${((angle * 180) / Math.PI) * (dense ? 0.65 : 0.2)}deg`,
      );
      button.style.setProperty("--asset-w", `${itemWidth}px`);
      button.style.setProperty("--asset-h", `${itemHeight}px`);
    });
  }

  function entrance(sourceRect) {
    const item = cases[active];
    layoutFan();
    const target = origin.getBoundingClientRect();
    const dx = sourceRect
      ? sourceRect.left + sourceRect.width / 2 - target.left - target.width / 2
      : 0;
    const dy = sourceRect
      ? sourceRect.top + sourceRect.height / 2 - target.top - target.height / 2
      : -50;
    const scale = sourceRect
      ? Math.min(
          sourceRect.width / target.width,
          sourceRect.height / target.height,
        )
      : 1.05;
    animate(
      origin,
      [
        {
          transform: `translate(-50%,-50%) translate(${dx}px,${dy}px) scale(${scale})`,
          opacity: 1,
        },
        {
          transform: "translate(-50%,-50%) translate(0,7px) scale(.98)",
          opacity: 1,
          offset: 0.78,
        },
        { transform: "translate(-50%,-50%)", opacity: 1 },
      ],
      { duration: 850, easing: "cubic-bezier(.22,1,.36,1)" },
    );
    stage.querySelectorAll(".fan-item").forEach((button, i) => {
      const transform = getComputedStyle(button).transform;
      animate(
        button,
        [
          {
            transform: `translate(-50%,-50%) translate(0,-12px) scale(.15)`,
            opacity: 0,
            filter: "blur(9px)",
          },
          { opacity: 1, filter: "blur(0)", offset: 0.55 },
          { transform, opacity: 1, filter: "blur(0)" },
        ],
        {
          duration: 900,
          delay: 130 + Math.abs(i - (item.count - 1) / 2) * 60,
          fill: "backwards",
          easing: "cubic-bezier(.16,1,.3,1)",
        },
      );
    });
  }

  function renderFan(sourceRect) {
    stopAnimations();
    stage.querySelectorAll(".fan-item").forEach((button) => button.remove());
    const item = cases[active];
    const ticket = ++generation;
    originImage.src = sourceURL(item);
    document.querySelector(".fan-error").textContent = "";
    for (let i = 0; i < item.count; i++) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "fan-item";
      button.setAttribute("aria-pressed", "false");
      button.innerHTML = `<img class="asset-image" src="${previewURL(item, i)}" alt="" width="190" height="245"><span class="asset-name"></span>`;
      button.addEventListener("click", () => {
        const pressed = button.getAttribute("aria-pressed") !== "true";
        stage
          .querySelectorAll(".fan-item")
          .forEach((other) => other.setAttribute("aria-pressed", "false"));
        button.setAttribute("aria-pressed", String(pressed));
      });
      stage.append(button);
    }
    updateFanCopy();
    entrance(sourceRect);
    preload(item).then((results) => {
      if (generation === ticket && results.some((ok) => !ok))
        document.querySelector(".fan-error").textContent = text([
          "部分预览未能加载，可查看完整结果。",
          "Some previews could not load. Open the full result below.",
        ]);
    });
  }

  function openFan(index, trigger) {
    if (closing) return;
    const sourceRect = trigger.querySelector("img").getBoundingClientRect();
    returnTarget = trigger;
    active = index;
    dialog.showModal();
    dialog.classList.remove("is-closing");
    trigger.setAttribute("aria-expanded", "true");
    renderFan(sourceRect);
    closeButton.focus({ preventScroll: true });
  }

  async function closeFan() {
    if (closing || !dialog.open) return;
    closing = true;
    stopAnimations();
    generation++;
    dialog.classList.add("is-closing");
    const target = returnTarget?.querySelector("img").getBoundingClientRect();
    const current = origin.getBoundingClientRect();
    stage.querySelectorAll(".fan-item").forEach((button, i) =>
      animate(
        button,
        [
          { transform: getComputedStyle(button).transform, opacity: 1 },
          {
            transform: "translate(-50%,-50%) scale(.1)",
            opacity: 0,
            filter: "blur(6px)",
          },
        ],
        {
          duration: 310,
          delay: Math.min(i * 12, 70),
          fill: "forwards",
          easing: "cubic-bezier(.4,0,.8,.2)",
        },
      ),
    );
    const sameSource =
      returnTarget?.dataset.openCase === String(active) ||
      (returnTarget === heroOriginal && selected === active);
    const dx =
      target && sameSource
        ? target.left + target.width / 2 - current.left - current.width / 2
        : 0;
    const dy =
      target && sameSource
        ? target.top + target.height / 2 - current.top - current.height / 2
        : -30;
    const scale =
      target && sameSource
        ? Math.min(target.width / current.width, target.height / current.height)
        : 0.85;
    const animation = animate(
      origin,
      [
        { transform: "translate(-50%,-50%)", opacity: 1 },
        {
          transform: `translate(-50%,-50%) translate(${dx}px,${dy}px) scale(${scale})`,
          opacity: sameSource ? 1 : 0,
        },
      ],
      {
        duration: 500,
        delay: 70,
        fill: "forwards",
        easing: "cubic-bezier(.22,1,.36,1)",
      },
    );
    await animation.finished.catch(() => {});
    dialog.close();
    returnTarget?.setAttribute("aria-expanded", "false");
    returnTarget?.focus({ preventScroll: true });
    stopAnimations();
    dialog.classList.remove("is-closing");
    closing = false;
  }

  heroOriginal.addEventListener("click", () => openFan(selected, heroOriginal));
  heroOriginal.addEventListener("pointerenter", () => preload(cases[selected]));
  closeButton.addEventListener("click", closeFan);
  origin.addEventListener("click", closeFan);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeFan();
  });
  dialog.addEventListener("click", (event) => {
    if (
      event.target === dialog ||
      event.target.classList.contains("fan-shell") ||
      event.target === stage ||
      event.target.classList.contains("fan-glow")
    )
      closeFan();
  });
  function stepCase(step) {
    if (closing) return;
    active = (active + step + cases.length) % cases.length;
    renderFan();
  }
  document
    .querySelectorAll("[data-step]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        stepCase(Number(button.dataset.step)),
      ),
    );
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      stepCase(event.key === "ArrowRight" ? 1 : -1);
    }
  });
  window.addEventListener("resize", () => {
    if (dialog.open && !closing) {
      stopAnimations();
      layoutFan();
    }
  });
  document.querySelectorAll("[data-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      category = button.dataset.filter;
      document
        .querySelectorAll("[data-filter]")
        .forEach((other) =>
          other.setAttribute("aria-pressed", String(other === button)),
        );
      grid.querySelectorAll(".case-card").forEach((card) => {
        card.hidden = category !== "all" && card.dataset.category !== category;
        card.classList.remove("case-enter");
        if (!card.hidden) {
          void card.offsetWidth;
          card.classList.add("case-enter");
        }
      });
      updateLibraryStatus();
    }),
  );
  function setLanguage(lang) {
    root.dataset.lang = lang;
    root.lang = lang === "zh" ? "zh-CN" : "en";
    langButton.textContent = lang === "zh" ? "EN" : "中";
    langButton.setAttribute(
      "aria-label",
      lang === "zh" ? "Switch to English" : "切换到中文",
    );
    renderLibrary();
    renderPicker();
    selectHero(selected);
    if (dialog.open) updateFanCopy();
    try {
      localStorage.setItem("ultrasplitter-language", lang);
    } catch (_) {}
  }
  langButton.addEventListener("click", () =>
    setLanguage(root.dataset.lang === "zh" ? "en" : "zh"),
  );
  document.querySelectorAll(".copy-btn").forEach((button) =>
    button.addEventListener("click", async () => {
      const previous = button.textContent;
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = text(["已复制", "COPIED"]);
      } catch (_) {
        button.textContent = text([
          "复制失败，请手动选择",
          "Select and copy manually",
        ]);
      }
      window.setTimeout(() => {
        button.textContent = previous;
      }, 1800);
    }),
  );
  let language = "zh";
  try {
    if (localStorage.getItem("ultrasplitter-language") === "en")
      language = "en";
  } catch (_) {}
  setLanguage(language);
})();
