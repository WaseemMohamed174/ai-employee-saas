import { Routes, Route } from "react-router-dom";
import Home from "@/pages/Home";
import Signup from "@/pages/Signup";
import Login from "@/pages/Login";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import VerifyEmail from "@/pages/VerifyEmail";
import DashboardLayout from "@/components/DashboardLayout";
import Dashboard from "@/pages/Dashboard";
import ApiKeys from "@/pages/ApiKeys";
import DatabasePage from "@/pages/Database";
import ConversationsPage from "@/pages/Conversations";
import ConversationDetailPage from "@/pages/ConversationDetail";
import ComplaintsPage from "@/pages/Complaints";
import ViolationsPage from "@/pages/Violations";
import CustomersPage from "@/pages/Customers";
import AlertsPage from "@/pages/Alerts";
import PersonaPage from "@/pages/Persona";
import SystemStatusPage from "@/pages/SystemStatus";
import ApiDocsPage, { PublicApiDocsPage } from "@/pages/ApiDocs";
import PlansUsagePage from "@/pages/PlansUsage";
import { AuthProvider } from "@/state/authStore";

// ============== APP ==============

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* ============== PUBLIC ROUTES ============== */}
        <Route path="/" element={<Home />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/api-docs" element={<PublicApiDocsPage />} />

        {/* ============== DASHBOARD ROUTES (protected) ============== */}
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="conversations/:id" element={<ConversationDetailPage />} />
          <Route path="complaints" element={<ComplaintsPage />} />
          <Route path="violations" element={<ViolationsPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="database" element={<DatabasePage />} />
          <Route path="persona" element={<PersonaPage />} />
          <Route path="system-status" element={<SystemStatusPage />} />
          <Route path="api-docs" element={<ApiDocsPage />} />
          <Route path="plans" element={<PlansUsagePage />} />
          <Route path="api-keys" element={<ApiKeys />} />
        </Route>

        {/* ============== 404 ============== */}
        <Route path="*" element={<Home />} />
      </Routes>
    </AuthProvider>
  );
}
