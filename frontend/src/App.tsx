import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./index.css";
import { ScenarioProvider } from "./hooks/useScenario";
import LandingPage from "./pages/LandingPage";
import PresetsPage from "./pages/PresetsPage";
import ScenarioBuilderPage from "./pages/ScenarioBuilderPage";
import SimulationPage from "./pages/SimulationPage";
import ValidationPage from "./pages/ValidationPage";

export default function App() {
  return (
    <ScenarioProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/simulate" element={<SimulationPage />} />
          <Route path="/build" element={<ScenarioBuilderPage />} />
          <Route path="/presets" element={<PresetsPage />} />
          <Route path="/validation" element={<ValidationPage />} />
        </Routes>
      </BrowserRouter>
    </ScenarioProvider>
  );
}
