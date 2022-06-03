class ConfirmDialog {
  constructor() {
    this.status = false;
    this.modal = $("#confirm-dialog");
    this.modalText = $("#confirm-dialog-text");
    this.cb = null;
    $("#confirm-dialog-confirm").click((e) => {
      if (this.cb) {
        this.cb();
        this.cb = null;
      }
    });
    this.modal.on("hidden.bs.modal", () => {
      this.cb = null;
    });
  }
  confirm(msg, cb) {
    this.modalText.html(msg);
    this.cb = cb;
    this.modal.modal("show");
    
  }
}

class App {
  constructor() {
    this.intervalCallbacks = [];
    this.getPicoStatusTimeOut = null;
    this.menuBtn = $("#menu-button");
    this.connectStatus = $("#connection-status");
    this.currentPage = "startPage";
    // start page

    this.deviceStatus = $("#device-status");
    // this.startTestBtn = $("#start-test");

    // wait Page
    this.waitReason = $("#wait-reason");
    this.cancelBtn = $("#cancel-run");

    // run page
    this.timeM1 = $("#time-minute-1");
    this.timeM2 = $("#time-minute-2");
    this.timeS1 = $("#time-second-1");
    this.timeS2 = $("#time-second-2");

    // result page
    this.resultIcon = $("#result-icon");
    this.resultTitle = $("#result-title");
    this.resultText = $("#result-text");
    this.reportBtn = $("#report-button");
    this.homeBtn = $("#home-button");

    //state
    this.selectedWifiSSID = null;
    this.appVersion = null;
    this.newAppVersionAvailable = false;

    // dialog
    this.confirmDialog = new ConfirmDialog();

    this.pages = {
      startPage: $("#startPage"),
      waitPage: $("#waitPage"),
      runPage: $("#runPage"),
      resultPage: $("#resultPage"),
      aboutPage: $("#aboutPage"),
      settingsPage: $("#settingsPage"),
    };

    this.initWebsocket();
    this.addEventListener();
  }

  initWebsocket() {
    // websocketAddr = "ws://ams-uda:8765";
    // if (websocketAddr.includes('websocketAddr')) {
    //     websocketAddr = "ws://ams-uda:8765"
    // }

    this.ws = new WebSocket(websocketAddr);

    this.ws.onopen = (e) => {
      this.connectStatus.html(
        '<span class="oi oi-link-intact text-light"></span>'
      );
      this.connectStatus.removeClass("btn-outline-warning");
      $('#reconnect-button').addClass('hidden');
      this.getPicoStatus();
      // this.send({ action: "heating.startTempControl" });
      this.send({ action: "main.getSystemID" });
      // this.send({ action: "main.getSystemSerial" });
      this.send({ action: "measurement.getVersion" });
      this.send({ action: "main.getVersion" });
      setTimeout(()=>{
        this.send({ action: "peripheral.scanWifi" });
        this.send({ action: "peripheral.getWifiSSID" });        
        this.send({ action: "main.getLatestVersion" });        
        this.send({ action: "main.syncSystemTime", timeString: new Date().toISOString()})    
      },5000)
    };

    this.ws.onclose = this.ws.onerror = (e) => {
      this.clearIntervalCallback();
      this.ws = null;
      this.connectStatus.html('<span class="oi oi-link-broken "></span>');
      this.connectStatus.addClass("btn-outline-warning");
      $('#reconnect-button').removeClass('hidden');
      this.showPage("startPage");
      $('#about-button').html('<span class="oi oi-menu"></span>')
      this.menuBtn.html('<span class="oi oi-cog"></span>')
      this.deviceStatus.text("Disconnected");
    };

    this.ws.onmessage = (e) => {
      let packet = JSON.parse(e.data);
      let data = packet.data;
      let action = packet.action;
      switch (action) {
        case "peripheral.scanWifi":
          let wifilist = "";
          Object.keys(data).forEach((ssid) => {
            const wifi = data[ssid];
            const secure =
              wifi.encryption === "on"
                ? '<span class="oi oi-lock-locked"></span>'
                : '<span class="oi oi-lock-unlocked"></span>';
            wifilist += `
                    <li class='list-group-item wifi-list-items' id="wifi-ssid-${wifi.ssid}">
                    <span class="oi oi-wifi"></span>
                     ${wifi.ssid} 
                     ${secure}
                     </li>
                    `;
          });
          $("#wifi-list").html(wifilist);
          this.addWifiItemListener();
          break;
        case "peripheral.getWifiSSID":
          $(`#wifi-ssid-${data}`).addClass("selected");
          break;
        case "main.getSystemID":
          $(".system-id").each(function () {
            $(this).text(data);
          });
          break;
        case "main.getVersion":
          $(".system-version").each(function () {
            $(this).text(data);
          });
          this.appVersion = data;
          break;
        case "measurement.getVersion":
          $(".firmware-version").each(function () {
            $(this).text(data);
          });
          this.appVersion = data;
          break;
        case "main.getLatestVersion":
          if (this.appVersion !== data) {
            $("#update-available").text(`New firmware ${data} is available.`);
            this.newAppVersionAvailable = true;
          }
          break;
        case "main.getSystemSerial":
          $(".system-serial").each(function () {
            $(this).text(data);
          });
          break;
        case "measurement.getPicoStatus":
          if (this.currentPage === 'settingsPage' || this.currentPage === 'aboutPage') {
            break
          }
          if (data.status == "idle") {
            this.deviceStatus.text("Ready");
            // this.startTestBtn.attr("disabled", false);
            // if just started and havn't return home
            if (data.started) {
              if (this.currentPage != "resultPage") {
                this.send({
                  action: "dataStore.getRecentPaginated",
                  page: 0,
                  perpage: 1,
                  returnRaw: false,
                });
                this.showPage("resultPage");
              }
            } else {
              this.showPage("startPage");
            }
          } else if (data.status == "waiting") {
            this.deviceStatus.text("Waiting");
            // this.startTestBtn.attr("disabled", true);
            let waitReason = data.reason || "";
            if (waitReason.includes("insert")) {
              waitReason = "Load Chip...";
            } else if (waitReason.includes("Fluid")) {
              waitReason = "Fluid Fill...";
            } else if (waitReason.includes("Heating")) {
              waitReason = "Heating Up...";
            } else if (waitReason.includes('signal abnormal')) {
              waitReason = 'Sensor abnormal...'
            }
            else {
              waitReason = "Waiting...";
            }
            this.waitReason.text(waitReason);
            this.showPage("waitPage");
          } else if (data.status == "running") {
            this.deviceStatus.text("Running");
            // this.startTestBtn.attr("disabled", true);
            let remain = Math.round(data.remainingTime);
            let seconds = (remain % 60).toString().padStart(2, "0");
            let minutes = Math.floor(remain / 60)
              .toString()
              .padStart(2, "0");
            this.timeM1.text(minutes[0]);
            this.timeM2.text(minutes[1]);
            this.timeS1.text(seconds[0]);
            this.timeS2.text(seconds[1]);
            this.showPage("runPage");
          } else if (data.status == "error") {
            this.deviceStatus.text("Error");
            // this.startTestBtn.attr("disabled", true);
            this.showPage("startPage");
          }
          this.getPicoStatusTimeOut = setTimeout(() => {
            this.getPicoStatus();
          }, 1000);
          break;
        case "dataStore.getRecentPaginated":
          // let status = data.items[0].status.stat;
          let result = data.items[0].result || "Invalid [N]";
          // in this version, result will be Positive, Negative , or Invalid [E,R,FTC]
          this.showResult(result);         
          break;
        case "measurement.stopPico":
          this.showToast({
            title: "Cancel Test",
            body: "<strong>Test canceled</strong><br>Return to home page.",
          });
          break;
        case "Chip Insertion Error":
          this.showToast({
            title: "Chip Error",
            body:
              "<strong>Chip Not Detected</strong><br>Plese check if chip is correctly loaded.",
          });
          break;
        case "Fluid Fill Error - C1":
        case "Fluid Fill Error - C2":
        case "Fluid Fill Error - C3":
        case "Fluid Fill Error - C4":
          this.showToast({
            title: "Fluid Fill",
            body: `<strong>${action}</strong><br>Plese check channels.`,
          });
          break;
        case "main.updateGit":
          this.showToast({
            title: "Firmware Updated",
            body: `<strong>Reader firmware updated.</strong><br>Please wait until reader restart.`,
          });
          this.send({action:'main.restartSystem'})
          break;
        case 'config.setAccountToken':
          this.showToast({
            title: "Set Account Token",
            body: `<strong>${data}</strong>`
          })
          break
        case "peripheral.setWifiPassword":
            this.showToast({
                title:"Wi-Fi",
                body:`<strong>Connecting to new Wi-Fi</strong><br>${data}<br>Connect your device to the same Wi-Fi network to access reader App.`
            })
            this.ws.close()
            break;
        default:
          console.log(packet);
          break;
      }
    };
  }

  

  showResult(result, ) {
    // set the reslt page according to result type, positive, negative or invalid    
    let r = result.toLowerCase()   
    switch (r) {
      case "positive":
        this.resultIcon.html('<span  class="oi oi-medical-cross text-danger" ></span>');
        this.resultTitle.text("COVID-19 Positive");
        this.resultText.html(
          "The Virus <span style='color:red'>WAS Detected</span>."
        );
        break;
      case "negative":
        this.resultIcon.html(
          '<span  class="oi oi-circle-check text-success" ></span>'
        );
        this.resultTitle.text("COVID-19 Negative");
        this.resultText.html(
          "The Virus <span style='color:green'>WAS NOT</span> Detected"
        );
        break;
      case "error":
          this.resultIcon.html(
            '<span  class="oi oi-warning text-warning" ></span>'
          );
          this.resultTitle.text("TEST ERROR");
          this.resultText.html(
            "An error occured during the test"
          );
          break;
      case "invalid":       
      default:
        this.resultIcon.html(
          '<span  class="oi oi-circle-x text-warning" ></span>'
        );
        this.resultTitle.text("Invalid Result");
        this.resultText.html(`Result: ${result.toUpperCase()}.`);
        break;        
    }
  }

  send(msg) {
    if (this.ws && this.ws.readyState == 1) {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }

  clearIntervalCallback() {
    this.intervalCallbacks.forEach((i) => {
      clearInterval(i);
    });
    this.intervalCallbacks = [];
  }

  getPicoStatus() {
    this.send({ action: "measurement.getPicoStatus" });
  }

  showPage(pageName) {
    if (pageName != this.currentPage) {
      this.pages[this.currentPage].fadeOut(200, () => {
        this.pages[pageName].fadeIn(200, () => {
          this.currentPage = pageName;
        });
      });
    }
  }

  showToast(msg) {
    let title = msg.title || "TOAST";
    let body = msg.body || "This is a toast message.";
    let time = new Date().toLocaleString().split(",")[1].trim();
    let toast = `
    <div class="toast" role="alert" aria-live="assertive" aria-atomic="true" >
    <div class="toast-header">
        <strong class="mr-auto">${title.toUpperCase()}</strong>
        <small class="text-muted">${time}</small>
        <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
        <span aria-hidden="true">&times;</span>
        </button>
    </div>
    <div class="toast-body">
        ${body}
    </div>
    </div>`;
    $("#toast-msg").append(toast);
    $(".toast").toast({
      autohide: false,
    });
    setTimeout(() => {
      $("#toast-msg .toast:first-child").fadeOut().remove();
    }, 15000);
    $(".toast").toast("show");
  }

  addWifiItemListener() {
    // select wifi from list
    $(".wifi-list-items").on("click", (e) => {
      $(".wifi-list-items").removeClass("selected");
      $(e.target).addClass("selected");
      this.selectedWifiSSID = e.target.id.replace("wifi-ssid-", "");
    });
  }

  addEventListener() {
    $("#wifi-connect").on("click", (e) => {
      if (!this.selectedWifiSSID) {
        return this.confirmDialog.confirm(
          "Please Select Wifi Connection From List."
        );
      }
      const pwd = $("#wifi-password").val();
      if (!pwd) {
        return this.confirmDialog.confirm("Please enter the wifi password.");
      }
      this.confirmDialog.confirm(
        `Connect to Wi-Fi network &lt;${this.selectedWifiSSID}&gt;?`,
        () => {
          this.send({
            action: "peripheral.setWifiPassword",
            ssid: this.selectedWifiSSID,
            pwd,
          });
        }
      );
    });

    $("#firmware-update").on("click", (e) => {
      if (this.newAppVersionAvailable) {
        this.confirmDialog.confirm("Update reader firmware?", () => {
          this.send({ action: "main.updateGit" });
        });
      }
    });

    $('#save-token').on('click',()=>{
      const token = $('#user-token').val()
      this.confirmDialog.confirm(`Set account token to ${token}?`,()=>{        
        this.send({action:'config.setAccountToken',token})
      })
    })

    this.connectStatus.on("click", (e) => {
      if (!this.ws || this.ws.readyState != 1) {
        this.initWebsocket();
      }
    });

    $('#reconnect-button').on("click", (e) => {
      if (!this.ws || this.ws.readyState != 1) {
        this.initWebsocket();
      }
    });

    // // start test
    // this.startTestBtn.on("click", (e) => {
    //   let w = this.startTestBtn.width();
    //   let x = e.pageX - this.startTestBtn.offset().left;
    //   let side =
    //     x / w < 0.3333 ? "negative" : x / w < 0.6666 ? "normal" : "positive";

    //   this.send({
    //     meta: {
    //       name: `Demo ${new Date().toLocaleTimeString()}`,
    //       exp: "Demo Run",
    //       desc: "Demo Run",
    //       __side: side,
    //     },
    //     method: runMethod === "{{runMethod}}" ? "demoRun" : runMethod,
    //     deltaT: 5,
    //     action: "measurement.startMeasure",
    //   });
    // });

    // cancel test
    this.cancelBtn.on("click", (e) => {
      this.confirmDialog.confirm("Sure to cancel test?", () => {
        this.send({ action: "measurement.stopPico" });
      });
    });

    // go home or new test
    this.reportBtn.on("click", (e) => {
      this.confirmDialog.confirm("Sure to report test result?", () => {
        //
        this.showToast({
          title: "Result Sent",
          body:
            "<strong>Test Result Reported</strong><br>Test result was reported successfully.",
        });
      });
    });
    // go home
    this.homeBtn.on("click", (e) => {
      this.send({ action: "measurement.resetTestStarted" }); // to close the page
      this.showPage("startPage");
    });

    // settings apge
    this.menuBtn.on("click", (e) => {
      if (this.currentPage === "settingsPage") {
        this.showPage("startPage");
        this.menuBtn.html('<span class="oi oi-cog"></span>')
        this.getPicoStatusTimeOut = setTimeout(() => {
          this.getPicoStatus();
        }, 1000);
      } else {
        clearTimeout(this.getPicoStatusTimeOut);
        this.getPicoStatusTimeOut = null;
        this.menuBtn.html('<span class="oi oi-x"></span>')
        this.showPage("settingsPage");
      }
      $('#about-button').html('<span class="oi oi-menu"></span>')
    });

    // about page
    $('#about-button').on("click", (e) => {
        if (this.currentPage === "aboutPage") {
          this.showPage("startPage");
          $('#about-button').html('<span class="oi oi-menu"></span>')          
          this.getPicoStatusTimeOut = setTimeout(() => {
            this.getPicoStatus();
          }, 1000);
        } else {
          clearTimeout(this.getPicoStatusTimeOut);
          this.getPicoStatusTimeOut = null;
          $('#about-button').html('<span class="oi oi-x"></span>')
          this.showPage("aboutPage");
        }
        this.menuBtn.html('<span class="oi oi-cog"></span>')
      });

    // download log button
    $('#download-log-button').on('click',e=>{
      window.open('/logs')
    })
    // download log button
    $('#download-rawdata-button').on('click',e=>{
      window.open('/download')
    })
    }
}

let app = new App();
