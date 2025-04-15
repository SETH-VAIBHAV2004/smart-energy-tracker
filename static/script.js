document.addEventListener("DOMContentLoaded", function () {
  const API_BASE = window.location.origin;
  let currentRange = "all";
  window.energyChart = null; // ✅ Declare globally
  let analyticsDebounceTimer = null;

  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const username = document.getElementById("register-username").value.trim();
      const password = document.getElementById("register-password").value.trim();

      if (!username || !password) {
        alert("Please enter both username and password.");
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ username, password }),
        });

        const data = await response.json();
        alert(data.message);
        if (response.ok && data.status === "success") {
          window.location.href = "/";
        }
      } catch (error) {
        alert("Registration failed. Try again later.");
      }
    });
  }

  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const username = document.getElementById("login-username").value.trim();
      const password = document.getElementById("login-password").value.trim();

      if (!username || !password) {
        alert("Please enter both username and password.");
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ username, password }),
        });

        const data = await response.json();
        if (response.ok && data.status === "success") {
          window.location.href = "/dashboard";
        } else {
          alert("Login failed: " + data.message);
        }
      } catch (error) {
        alert("Login failed. Try again later.");
      }
    });
  }

  // Add debounce function
  function debounce(func, wait) {
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(analyticsDebounceTimer);
        func(...args);
      };
      clearTimeout(analyticsDebounceTimer);
      analyticsDebounceTimer = setTimeout(later, wait);
    };
  }

  // Debounced version of fetchAnalytics
  const debouncedFetchAnalytics = debounce(fetchAnalytics, 1000);

  const submitEnergyBtn = document.getElementById("submit-energy");
  if (submitEnergyBtn) {
    submitEnergyBtn.addEventListener("click", async function () {
      const solar = parseFloat(document.getElementById("solar-energy").value);
      const electric = parseFloat(document.getElementById("electric-energy").value);

      if (isNaN(solar) || isNaN(electric)) {
        alert("Please enter valid numeric values for energy consumption.");
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/add_energy`, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "Accept": "application/json"
          },
          credentials: "include",
          body: JSON.stringify({
            date: new Date().toISOString().split("T")[0],
            solar_energy: solar,
            electric_energy: electric,
            temperature: 25,
            humidity: 60
          }),
        });

        const data = await response.json();
        
        if (!response.ok) {
          console.error("Server error details:", data);
          throw new Error(data.message || `Server error: ${response.status}`);
        }

        if (data.status === "success") {
          alert("Energy data submitted successfully!");
          // Clear the form
          document.getElementById("solar-energy").value = "";
          document.getElementById("electric-energy").value = "";
          // Refresh the data
          await fetchEnergyData(currentRange);
        } else {
          console.error("Error response:", data);
          throw new Error(data.message || "Failed to submit energy data");
        }
      } catch (error) {
        console.error("Submit energy error:", error);
        alert(`Error: ${error.message}\n\nPlease try again or contact support if the problem persists.`);
      }
    });
  }

  async function fetchEnergyData(range = "all") {
    const chartCanvas = document.getElementById("energyChart");
    const fromDate = document.getElementById("start-date")?.value;
    const toDate = document.getElementById("end-date")?.value;

    let url = `${API_BASE}/get_energy_data`;

    if (range !== "all") {
      url += `?range=${range}`;
    } else if (fromDate && toDate) {
      url = `${API_BASE}/get_energy_data?from_date=${fromDate}&to_date=${toDate}`;
    }

    try {
      const response = await fetch(url, {
        method: "GET",
        credentials: "include",
      });

      const result = await response.json();
      if (response.ok && result.status === "success") {
        const data = result.data;
        updateEnergyTable(data);
        updateEnergyChart(data);
        updateTotals(data);
        // Call debounced analytics after data update
        debouncedFetchAnalytics();
      } else {
        console.error("Could not retrieve energy data:", result.message);
      }
    } catch (error) {
      console.error("Fetch Error:", error);
    }
  }

  // Helper function to update energy table
  function updateEnergyTable(data) {
    const tbody = document.querySelector("#energy-table tbody");
    if (!tbody) return;
    
    tbody.innerHTML = "";
    data.forEach((entry) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${entry.date || 'N/A'}</td>
        <td>${(parseFloat(entry.solar_energy) || 0).toFixed(2)}</td>
        <td>${(parseFloat(entry.electric_energy) || 0).toFixed(2)}</td>
        <td><button class="btn btn-sm btn-danger delete-btn" data-id="${entry.id}">Delete</button></td>
      `;
      tbody.appendChild(row);
    });

    // Add delete button handlers
    document.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", async function () {
        const entryId = this.getAttribute("data-id");
        if (confirm(`Delete entry ID ${entryId}?`)) {
          await deleteEntry(entryId);
        }
      });
    });
  }

  // Helper function to update energy chart
  function updateEnergyChart(data) {
    const chartCanvas = document.getElementById("energyChart");
    if (!chartCanvas) return;

    const labels = data.map(entry => entry.date);
    const solarData = data.map(entry => parseFloat(entry.solar_energy) || 0);
    const electricData = data.map(entry => parseFloat(entry.electric_energy) || 0);

    const ctx = chartCanvas.getContext("2d");
    if (window.energyChart && typeof window.energyChart.destroy === "function") {
      window.energyChart.destroy();
    }

    window.energyChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Solar Energy",
            backgroundColor: "rgba(243, 156, 18, 0.2)",
            borderColor: "#f39c12",
            data: solarData,
            fill: true,
            tension: 0.4
          },
          {
            label: "Electric Energy",
            backgroundColor: "rgba(41, 128, 185, 0.2)",
            borderColor: "#2980b9",
            data: electricData,
            fill: true,
            tension: 0.4
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Energy (kWh)'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Date'
            }
          }
        },
        plugins: {
          legend: {
            position: 'top',
          },
          title: {
            display: true,
            text: 'Energy Consumption Over Time'
          }
        }
      },
    });
  }

  // Helper function to update totals
  function updateTotals(data) {
    const totalSolar = data.reduce((sum, entry) => sum + (parseFloat(entry.solar_energy) || 0), 0);
    const totalElectric = data.reduce((sum, entry) => sum + (parseFloat(entry.electric_energy) || 0), 0);
    
    const totalSolarElement = document.getElementById("total-solar");
    const totalElectricElement = document.getElementById("total-electric");
    
    if (totalSolarElement) totalSolarElement.textContent = totalSolar.toFixed(2);
    if (totalElectricElement) totalElectricElement.textContent = totalElectric.toFixed(2);
  }

  async function deleteEntry(entryId) {
    try {
      const response = await fetch(`${API_BASE}/delete_entry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ id: entryId }),
      });

      const data = await response.json();
      if (response.ok && data.status === "success") {
        await fetchEnergyData(currentRange);
        // Analytics will be fetched by fetchEnergyData
      } else {
        throw new Error(data.message || "Failed to delete entry");
      }
    } catch (error) {
      console.error("Delete entry error:", error);
      alert("Failed to delete the entry: " + error.message);
    }
  }

  const filterButtons = document.querySelectorAll(".filter-btn");
  filterButtons.forEach((button) => {
    button.addEventListener("click", function () {
      currentRange = this.getAttribute("data-range");
      fetchEnergyData(currentRange);
    });
  });

  const applyDateFilterBtn = document.getElementById("filter-btn");
  if (applyDateFilterBtn) {
    applyDateFilterBtn.addEventListener("click", () => {
      currentRange = "all";
      fetchEnergyData(currentRange);
    });
  }

  const logoutBtn = document.getElementById("logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      fetch(`${API_BASE}/logout`, {
        method: "GET",
        credentials: "include",
      }).then(() => {
        window.location.href = "/";
      });
    });
  }

  async function fetchEnergySavings() {
    const savingsDiv = document.getElementById("savings-result");
    if (!savingsDiv) return;

    try {
      const response = await fetch(`${API_BASE}/calculate_savings`, {
        method: "GET",
        credentials: "include",
      });
      const data = await response.json();

      if (data.status === "success") {
        savingsDiv.textContent = `Estimated Savings: ₹${data.savings.toFixed(2)}`;
      } else {
        savingsDiv.textContent = "Unable to calculate savings.";
      }
    } catch (error) {
      savingsDiv.textContent = "Error fetching savings data.";
    }
  }

  async function fetchEnergyTips() {
    const tipsDiv = document.getElementById("energy-tips");
    if (!tipsDiv) return;

    try {
      const response = await fetch(`${API_BASE}/energy_tips`, {
        method: "GET",
        credentials: "include",
      });
      const data = await response.json();

      if (data.status === "success") {
        tipsDiv.innerHTML = "";
        data.tips.forEach((tip) => {
          const li = document.createElement("li");
          li.textContent = tip;
          tipsDiv.appendChild(li);
        });
      } else {
        tipsDiv.innerHTML = "<li>Unable to fetch tips.</li>";
      }
    } catch (error) {
      tipsDiv.innerHTML = "<li>Error loading tips.</li>";
    }
  }

  async function fetchAnalytics() {
    try {
      console.log("Fetching analytics data...");
      const response = await fetch(`${API_BASE}/get_analytics`, {
        method: "GET",
        credentials: "include",
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      console.log("Analytics response:", JSON.stringify(data, null, 2));

      if (response.ok && data.status === "success") {
        const analysis = data.analysis;
        console.log("Processing analytics data:", JSON.stringify(analysis, null, 2));
        
        if (!analysis) {
          console.error("No analysis data in response");
          throw new Error("No analysis data available");
        }
        
        // Update analytics display with more robust checks
        const currentPattern = document.getElementById("current-pattern");
        console.log("Current pattern element:", currentPattern);
        console.log("Current pattern value:", analysis.current_pattern);
        if (currentPattern) {
          currentPattern.textContent = 
            `Current consumption pattern: ${(analysis.current_pattern || 0).toFixed(2)} kWh`;
        }
        
        const nextHourPred = document.getElementById("next-hour-pred");
        console.log("Next hour prediction element:", nextHourPred);
        console.log("Next hour prediction value:", analysis.next_hour_prediction);
        if (nextHourPred) {
          nextHourPred.textContent = 
            `Predicted next hour: ${(analysis.next_hour_prediction || 0).toFixed(2)} kWh`;
        }
        
        const carbonFootprint = document.getElementById("carbon-footprint");
        console.log("Carbon footprint element:", carbonFootprint);
        console.log("Carbon footprint value:", analysis.carbon_footprint);
        if (carbonFootprint) {
          carbonFootprint.textContent = 
            `Total carbon footprint: ${(analysis.carbon_footprint || 0).toFixed(2)} kg CO2`;
        }
        
        const energyCost = document.getElementById("energy-cost");
        console.log("Energy cost element:", energyCost);
        console.log("Energy cost value:", analysis.energy_cost);
        if (energyCost) {
          energyCost.textContent = 
            `Total energy cost: $${(analysis.energy_cost || 0).toFixed(2)}`;
        }
        
        // Update recommendations with better error handling
        const recommendationsList = document.getElementById("recommendations");
        console.log("Recommendations element:", recommendationsList);
        console.log("Recommendations data:", analysis.recommendations);
        if (recommendationsList) {
          recommendationsList.innerHTML = "";
          
          if (analysis.recommendations?.carbon?.length > 0) {
            const carbonHeader = document.createElement("li");
            carbonHeader.innerHTML = "<strong>Carbon Reduction Tips:</strong>";
            recommendationsList.appendChild(carbonHeader);
            
            analysis.recommendations.carbon.forEach(rec => {
              const li = document.createElement("li");
              li.textContent = rec;
              recommendationsList.appendChild(li);
            });
          }
          
          if (analysis.recommendations?.cost?.length > 0) {
            const costHeader = document.createElement("li");
            costHeader.innerHTML = "<strong>Cost Saving Tips:</strong>";
            recommendationsList.appendChild(costHeader);
            
            analysis.recommendations.cost.forEach(rec => {
              const li = document.createElement("li");
              li.textContent = rec;
              recommendationsList.appendChild(li);
            });
          }

          if (!analysis.recommendations?.carbon?.length && !analysis.recommendations?.cost?.length) {
            const li = document.createElement("li");
            li.textContent = "No recommendations available at this time.";
            recommendationsList.appendChild(li);
          }
        }
      } else {
        console.error("Analytics error:", data.message || "Unknown error");
        throw new Error(data.message || "Failed to get analytics data");
      }
    } catch (error) {
      console.error("Analytics fetch error:", error);
      // Show error state in the UI
      const elements = ["current-pattern", "next-hour-pred", "carbon-footprint", "energy-cost"];
      elements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
          element.innerHTML = `<span class="text-danger">Error loading data</span>`;
        }
      });
      
      const recommendationsList = document.getElementById("recommendations");
      if (recommendationsList) {
        recommendationsList.innerHTML = '<li class="text-danger">Error loading recommendations</li>';
      }
    }
  }

  if (window.location.pathname.includes("dashboard")) {
    console.log("Dashboard loaded, fetching initial data...");
    fetchEnergyData(currentRange);
  }
});
