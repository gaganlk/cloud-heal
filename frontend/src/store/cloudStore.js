import { create } from 'zustand'

export const useCloudStore = create((set) => ({
  credentials: [],
  selectedCredential: null,
  resources: [],
  graphData: null,
  scanStatus: {},
  predictions: [],
  healingActions: [],

  setCredentials: (creds) => set({ credentials: creds }),
  addCredential: (cred) => set((s) => ({ credentials: [...s.credentials, cred] })),
  removeCredential: (id) => set((s) => ({
    credentials: s.credentials.filter((c) => c.id !== id),
  })),
  setSelectedCredential: (cred) => set({ selectedCredential: cred }),
  setResources: (resources) => set({ resources }),
  setGraphData: (data) => set({ graphData: data }),
  setScanStatus: (credId, status) => set((s) => ({
    scanStatus: { ...s.scanStatus, [credId]: status },
  })),
  setPredictions: (predictions) => set({ predictions }),
  setHealingActions: (actions) => set({ healingActions: actions }),
}))
