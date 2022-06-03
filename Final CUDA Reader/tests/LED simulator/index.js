class LED {
  constructor() {
    this.led1 = { e: document.getElementById("led1"), a: null };
    this.led2 = { e: document.getElementById("led2"), a: null };
    this.led3 = { e: document.getElementById("led3"), a: null };    
  }

  color(c) {
    return {
      r: "#ff3838",
      g: "#5fff59",
      b: "blue",
      y: "yellow",
      p: "magenta",
      w: "white",
      k: "#585858",
    }[c];
  }

  setLed(led, color) {
    let L = { 1: this.led1, 2: this.led2, 3: this.led3 }[led];
    if (L.a) {
      clearTimeout(L.a);
    }
    setTimeout(() => {
      L.e.style.backgroundColor = this.color(color);
      if (color!='k') {
        L.e.style.boxShadow = `0px 0px 5px ${this.color(color)}`;
      } else {
        L.e.style.boxShadow = '';
      }  
    }, 1);
  }

  blinkLed(led, colors, times,i=0) {
    let L = { 1: this.led1, 2: this.led2, 3: this.led3 }[led];
    if (L.a) {
      clearTimeout(L.a);
    }    
    L.a = setTimeout(() => {
      let color = this.color(colors[i % colors.length])
      L.e.style.backgroundColor = color;
      if (colors[i % colors.length] !='k') {
        L.e.style.boxShadow = `0px 0px 5px ${color}`;
      } else {
        L.e.style.boxShadow = '';
      }     
      this.blinkLed(led, colors, times, i + 1);
    }, times[(i-1) % times.length]);
  }

  ledoff(led) {
    this.setLed(led, 'k');
  }
  clear() {
    this.ledoff(1);
    this.ledoff(2);
    this.ledoff(3);
  }
}

function OnClick(id,cb) {
    document.getElementById(id).addEventListener('click', cb);
}

led = new LED();

var P = 3, N = 1, S = 2;
P = localStorage.getItem('P') || P;
N = localStorage.getItem('N') || N;
S = localStorage.getItem('S') || S;
document.getElementById('N').value = N;
document.getElementById('P').value = P;
document.getElementById('S').value = S;

document.getElementById('N').addEventListener('change', () => {
    N = document.getElementById('N').value
    localStorage.setItem('N', N);
})
document.getElementById('S').addEventListener('change', () => {
    S = document.getElementById('S').value
    localStorage.setItem('S', S);
})
document.getElementById('P').addEventListener('change', () => {
    P = document.getElementById('P').value
    localStorage.setItem('P', P);
})

OnClick('positive', () => {    
    led.setLed(P,'r')
    led.ledoff(N);
})

OnClick('negative', () => {
    led.setLed(N,'g')
    led.ledoff(P);
})

OnClick('invalid', () => {
    led.setLed(N,'y')
    led.setLed(P,'y')
    // led.blinkLed(N,['y','k'],[500,500])
    // led.blinkLed(P,['y','k'],[500,500])
})


OnClick('result-error', () => {
    led.blinkLed(N,['p','k'],[500,400])
    led.blinkLed(P,['p','k'],[500,400])
})

OnClick('idle', () => {
    led.ledoff(N);
    led.ledoff(P);
})

OnClick('test-error', () => {
    led.blinkLed(N,['r','k'],[500,550])
    led.blinkLed(P,['r','k'],[500,550])    
})

OnClick('waiting', () => {
    led.blinkLed(N,['y','k'],[400,400])
    setTimeout(() => {led.blinkLed(P,['y','k'],[400,400])},200)
})

OnClick('running', () => {
    led.blinkLed(N,'wk',[900,700])
    setTimeout(() => {
        led.blinkLed(P,'wk',[900,700])},800)
})


OnClick('wifi-ap', () => {
    led.setLed(S,'w')
})

OnClick('wifi-client', () => {
    led.setLed(S,'g')
})

OnClick('wifi-error', () => {
    led.blinkLed(S,['p', 'k'],[500,500])
})

OnClick('pico-error', () => {
    led.blinkLed(S,['r', 'k'],[500,500])
})

OnClick('reset-btn', () => {
    led.blinkLed(S,'wk',[500,500])
})

OnClick('power-on', () => {
    led.blinkLed(S,'wk',[500,500])
})



OnClick('clear', () => {
    led.clear()
})
