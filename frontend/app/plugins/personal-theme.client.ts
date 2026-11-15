import "~/assets/personal/liquid-glass.css";
import { usePersonalLook } from "~/composables/personal/use-personal-look";

/** Loads the look of the personal edition and applies the choice that the person saved. */
export default defineNuxtPlugin(() => {
  usePersonalLook();
});
