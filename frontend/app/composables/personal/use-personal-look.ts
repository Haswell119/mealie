const STORAGE_KEY = "pe-glass";
const glass = ref(true);
let loaded = false;

function apply(value: boolean) {
  if (import.meta.client) {
    document.documentElement.classList.toggle("pe-glass", value);
  }
}

/**
 * The look of the personal edition. The "liquid glass" look is on by default; a person who finds it hard
 * to read, or whose device is slow, can turn it off and get the stock look of Mealie back.
 */
export function usePersonalLook() {
  if (!loaded && import.meta.client) {
    loaded = true;
    try {
      glass.value = window.localStorage.getItem(STORAGE_KEY) !== "off";
    }
    catch {
      glass.value = true;
    }
    apply(glass.value);
  }

  function setGlass(value: boolean) {
    glass.value = value;
    apply(value);
    try {
      window.localStorage.setItem(STORAGE_KEY, value ? "on" : "off");
    }
    catch {
      // Private browsing can refuse storage: the choice then lasts for the page only.
    }
  }

  return { glass: readonly(glass), setGlass };
}
