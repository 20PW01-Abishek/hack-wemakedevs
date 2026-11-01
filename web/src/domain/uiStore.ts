import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface UiState {
  collapsed: boolean;
  toggleSidebar: () => void;
}

/** Layout preferences that survive a reload. */
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      collapsed: false,
      toggleSidebar: () => set((s) => ({ collapsed: !s.collapsed })),
    }),
    { name: "lattice-ui", storage: createJSONStorage(() => localStorage), skipHydration: true },
  ),
);
