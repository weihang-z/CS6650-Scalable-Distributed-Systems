CREATE TABLE shopping_carts (
    shopping_cart_id INT NOT NULL AUTO_INCREMENT,
    customer_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (shopping_cart_id),
    INDEX idx_shopping_carts_customer_id_updated_at (customer_id, updated_at)
) ENGINE=InnoDB;

CREATE TABLE shopping_cart_items (
    cart_item_id BIGINT NOT NULL AUTO_INCREMENT,
    shopping_cart_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (cart_item_id),
    CONSTRAINT fk_cart_items_cart
        FOREIGN KEY (shopping_cart_id)
        REFERENCES shopping_carts(shopping_cart_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_cart_items_quantity
        CHECK (quantity >= 1),
    UNIQUE KEY uq_cart_product (shopping_cart_id, product_id)
) ENGINE=InnoDB;