var createCheckoutSession = function(priceId) {
    return fetch("/create-checkout-session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        priceId: priceId
      })
    }).then(function(result) {
      return result.json();
    });
  };

const BASIC_PRICE_ID = "price_1KdhTRCsKWtKuHp0mWu6B081";
const stripe = Stripe("pk_test_51KdgypCsKWtKuHp0d4s9tClCkMobMKjSyxbsEDqs7IdMgKyQMIapS7bQJI0Cd2awD6yGPPNCv5jUVGpx6p0LZAbl002NA2GyVG");

document.addEventListener("DOMContentLoaded", function(event) {
    document
    .getElementById("checkout-basic")
    .addEventListener("click", function(evt) {
        createCheckoutSession(BASIC_PRICE_ID).then(function(data) {
            stripe
                .redirectToCheckout({
                    sessionId: data.sessionId
                });
            });
        });

});